from __future__ import unicode_literals, division, absolute_import, print_function
import atexit
from contextlib import contextmanager
import signal
import os
import sys
import shutil
import logging
import threading
import pkg_resources
import yaml
from datetime import datetime, timedelta

import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import SingletonThreadPool
from sqlalchemy.exc import OperationalError

# These need to be declared before we start importing from other flexget modules, since they might import them
Base = declarative_base()
Session = sessionmaker()

from flexget import config_schema, db_schema
from flexget.event import fire_event
from flexget.ipc import IPCServer, IPCClient
from flexget.scheduler import Scheduler
from flexget.utils.tools import pid_exists

log = logging.getLogger('manager')

manager = None
DB_CLEANUP_INTERVAL = timedelta(days=7)


@sqlalchemy.event.listens_for(Session, 'before_commit')
def before_commit(session):
    if not manager.has_lock and session.dirty:
        log.debug('BUG?: Database writes should not be tried when there is no database lock.')


class Manager(object):

    """Manager class for FlexGet

    Fires events:

    * manager.startup

      After manager has been initialized. This is when application becomes ready to use, however no database lock is
      present, so the database must not be modified on this event.

    * manager.lock-acquired

      The manager does not always require a lock on startup, if one is requested, this event will run when it has been
      acquired successfully

    * manager.config-loaded

      When a valid configuration has been (re)loaded, this event is fired

    * manager.upgrade

      If any plugins have declared a newer schema version than exists in the database, this event will be fired to
      allow plugins to upgrade their tables

    * manager.shutdown

      When the manager is exiting

    * manager.execute.completed

      If execution in current process was completed

    * manager.daemon.started
    * manager.daemon.completed
    * manager.db_cleanup
    """

    unit_test = False
    options = None

    def __init__(self, options):
        """
        :param options: argparse parsed options object
        """
        global manager
        assert not manager, 'Only one instance of Manager should be created at a time!'
        self.options = options
        self.config_base = None
        self.config_name = None
        self.config_path = None
        self.db_filename = None
        self.engine = None
        self.lockfile = None
        self.database_uri = None
        self.db_upgraded = False
        self._has_lock = False

        self.config = {}

        self.scheduler = Scheduler(self)
        self.ipc_server = IPCServer(self, options.ipc_port)
        manager = self
        self.initialize()

        # cannot be imported at module level because of circular references
        from flexget.utils.simple_persistence import SimplePersistence
        self.persist = SimplePersistence('manager')

        log.debug('sys.defaultencoding: %s' % sys.getdefaultencoding())
        log.debug('sys.getfilesystemencoding: %s' % sys.getfilesystemencoding())
        log.debug('os.path.supports_unicode_filenames: %s' % os.path.supports_unicode_filenames)

        if db_schema.upgrade_required():
            log.info('Database upgrade is required. Attempting now.')
            # Make sure not to fire the lock-acquired event yet
            # TODO: Detect if any database upgrading is needed and acquire the lock only in one place
            with self.acquire_lock(event=False):
                fire_event('manager.upgrade', self)
                if manager.db_upgraded:
                    fire_event('manager.db_upgraded', self)
        fire_event('manager.startup', self)

    def __del__(self):
        global manager
        manager = None

    def initialize(self):
        """Separated from __init__ so that unit tests can modify options before loading config."""
        self.setup_yaml()
        self.find_config(create=(self.options.cli_command == 'webui'))
        self.init_sqlalchemy()
        fire_event('manager.before_config_load', self)
        self.load_config()
        fire_event('manager.before_config_validate', self)
        errors = self.validate_config()
        if errors:
            for error in errors:
                log.critical("[%s] %s", error.json_pointer, error.message)
            self.shutdown(finish_queue=False)
            sys.exit(1)
        fire_event('manager.config-loaded', self)

    @property
    def tasks(self):
        """A list of tasks in the config"""
        if not self.config:
            return []
        return self.config.get('tasks', {}).keys()

    @property
    def has_lock(self):
        return self._has_lock

    def run_cli_command(self):
        """
        Starting point when executing from commandline, dispatch execution
        to correct destination.

        * :meth:`.execute_command`
        * :meth:`.daemon_command`
        * :meth:`.webui_command`
        * CLI plugin callback function
        """
        command = self.options.cli_command
        options = getattr(self.options, command)
        # First check for built-in commands
        if command == 'execute':
            self.execute_command(options)
        elif command == 'daemon':
            self.daemon_command(options)
        elif command == 'webui':
            self.webui_command(options)
        else:
            # Otherwise dispatch the command to the callback function
            options.cli_command_callback(self, options)

    def execute_command(self, options):
        """
        Send execute command to daemon through IPC or perform execution
        on current process.

        Fires events:

        * manager.execute.completed

        :param options: argparse options
        """
        # If a daemon is started, send the execution to the daemon
        ipc_info = self.check_ipc_info()
        if ipc_info:
            client = IPCClient(ipc_info['port'], ipc_info['password'])
            client.execute(dict(options))
            self.shutdown()
            return
        # Otherwise we run the execution ourselves
        with self.acquire_lock():
            fire_event('manager.execute.started', self)
            self.scheduler.start(run_schedules=False)
            self.scheduler.execute(options)
            self.scheduler.shutdown(finish_queue=True)
            try:
                self.scheduler.wait()
            except KeyboardInterrupt:
                log.error('Got ctrl-c exiting after this task completes. Press ctrl-c again to abort this task.')
            else:
                fire_event('manager.execute.completed', self)
            self.shutdown(finish_queue=False)

    def daemon_command(self, options):
        """
        Fires events:

        * manager.daemon.started
        * manager.daemon.completed

        :param options: argparse options
        """
        if options.action == 'start':
            if options.daemonize:
                self.daemonize()
            with self.acquire_lock():
                signal.signal(signal.SIGTERM, self._handle_sigterm)
                self.ipc_server.start()
                fire_event('manager.daemon.started', self)
                self.scheduler.start()
                try:
                    self.scheduler.wait()
                except KeyboardInterrupt:
                    log.info('Got ctrl-c, shutting down.')
                    fire_event('manager.daemon.completed', self)
                    self.shutdown(finish_queue=False)
        elif options.action == 'stop':
            ipc_info = self.check_ipc_info()
            if ipc_info:
                client = IPCClient(ipc_info['port'], ipc_info['password'])
                client.shutdown()
                self.shutdown()
            else:
                log.error('There does not appear to be a daemon running.')
        elif options.action == 'status':
            ipc_info = self.check_ipc_info()
            if ipc_info:
                log.info('Daemon running. (PID: %s)' % ipc_info['pid'])
            else:
                log.info('No daemon appears to be running for this config.')

    def webui_command(self, options):
        """
        :param options: argparse options
        """
        try:
            pkg_resources.require('flexget[webui]')
        except pkg_resources.DistributionNotFound as e:
            log.error('Dependency not met. %s' % e)
            log.error('Webui dependencies not installed. You can use `pip install flexget[webui]` to install them.')
            self.shutdown()
            return
        if options.daemonize:
            self.daemonize()
        from flexget.ui import webui
        with self.acquire_lock():
            webui.start(self)

    def _handle_sigterm(self, signum, frame):
        log.info('Got SIGTERM. Shutting down.')
        self.shutdown(finish_queue=False)

    def setup_yaml(self):
        """Sets up the yaml loader to return unicode objects for strings by default"""

        def construct_yaml_str(self, node):
            # Override the default string handling function
            # to always return unicode objects
            return self.construct_scalar(node)
        yaml.Loader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)
        yaml.SafeLoader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)

        # Set up the dumper to not tag every string with !!python/unicode
        def unicode_representer(dumper, uni):
            node = yaml.ScalarNode(tag=u'tag:yaml.org,2002:str', value=uni)
            return node
        yaml.add_representer(unicode, unicode_representer)

        # Set up the dumper to increase the indent for lists
        def increase_indent_wrapper(func):

            def increase_indent(self, flow=False, indentless=False):
                func(self, flow, False)
            return increase_indent

        yaml.Dumper.increase_indent = increase_indent_wrapper(yaml.Dumper.increase_indent)
        yaml.SafeDumper.increase_indent = increase_indent_wrapper(yaml.SafeDumper.increase_indent)

    def find_config(self, create=False):
        """
        Find the configuration file.

        :param bool create: If a config file is not found, and create is True, one will be created in the home folder
        """
        config = None
        home_path = os.path.join(os.path.expanduser('~'), '.flexget')
        options_config = os.path.expanduser(self.options.config)

        possible = []
        if os.path.isabs(options_config):
            # explicit path given, don't try anything
            config = options_config
            possible = [config]
        else:
            log.debug('Figuring out config load paths')
            possible.append(os.getcwd())
            # for virtualenv / dev sandbox
            if hasattr(sys, 'real_prefix'):
                log.debug('Adding virtualenv path')
                possible.append(sys.prefix)
            # normal lookup locations
            possible.append(home_path)
            if sys.platform.startswith('win'):
                # On windows look in ~/flexget as well, as explorer does not let you create a folder starting with a dot
                home_path = os.path.join(os.path.expanduser('~'), 'flexget')
                possible.append(home_path)
            else:
                # The freedesktop.org standard config location
                xdg_config = os.environ.get('XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config'))
                possible.append(os.path.join(xdg_config, 'flexget'))

            for path in possible:
                config = os.path.join(path, options_config)
                if os.path.exists(config):
                    log.debug('Found config: %s' % config)
                    break
            else:
                config = None

        if not (config and os.path.exists(config)):
            if not create:
                log.info('Tried to read from: %s' % ', '.join(possible))
                log.critical('Failed to find configuration file %s' % options_config)
                sys.exit(1)
            config = os.path.join(home_path, options_config)
            log.info('Config file %s not found. Creating new config %s' % (options_config, config))
            with open(config, 'w') as newconfig:
                # Write empty tasks to the config
                newconfig.write(yaml.dump({'tasks': {}}))

        log.debug('Config file %s selected' % config)
        self.config_path = config
        self.config_name = os.path.splitext(os.path.basename(config))[0]
        self.config_base = os.path.normpath(os.path.dirname(config))
        self.lockfile = os.path.join(self.config_base, '.%s-lock' % self.config_name)

    def load_config(self):
        """
        .. warning::

           Calls sys.exit(1) if configuration file could not be loaded.
           This is something we probably want to change.
        """
        with open(self.config_path, 'rb') as f:
            config = f.read()
        try:
            config = config.decode('utf-8')
        except UnicodeDecodeError:
            log.critical('Config file must be UTF-8 encoded.')
            sys.exit(1)
        try:
            self.config = yaml.safe_load(config) or {}
        except Exception as e:
            msg = str(e).replace('\n', ' ')
            msg = ' '.join(msg.split())
            log.critical(msg)
            print('')
            print('-' * 79)
            print(' Malformed configuration file (check messages above). Common reasons:')
            print('-' * 79)
            print('')
            print(' o Indentation error')
            print(' o Missing : from end of the line')
            print(' o Non ASCII characters (use UTF8)')
            print(' o If text contains any of :[]{}% characters it must be single-quoted ' \
                  '(eg. value{1} should be \'value{1}\')\n')

            # Not very good practice but we get several kind of exceptions here, I'm not even sure all of them
            # At least: ReaderError, YmlScannerError (or something like that)
            if hasattr(e, 'problem') and hasattr(e, 'context_mark') and hasattr(e, 'problem_mark'):
                lines = 0
                if e.problem is not None:
                    print(' Reason: %s\n' % e.problem)
                    if e.problem == 'mapping values are not allowed here':
                        print(' ----> MOST LIKELY REASON: Missing : from end of the line!')
                        print('')
                if e.context_mark is not None:
                    print(' Check configuration near line %s, column %s' % (e.context_mark.line, e.context_mark.column))
                    lines += 1
                if e.problem_mark is not None:
                    print(' Check configuration near line %s, column %s' % (e.problem_mark.line, e.problem_mark.column))
                    lines += 1
                if lines:
                    print('')
                if lines == 1:
                    print(' Fault is almost always in this or previous line\n')
                if lines == 2:
                    print(' Fault is almost always in one of these lines or previous ones\n')

            # When --debug escalate to full stacktrace
            if self.options.debug:
                raise
            sys.exit(1)

        # config loaded successfully
        log.debug('config_name: %s' % self.config_name)
        log.debug('config_base: %s' % self.config_base)

    def save_config(self):
        """Dumps current config to yaml config file"""
        config_file = file(os.path.join(self.config_base, self.config_name) + '.yml', 'w')
        try:
            config_file.write(yaml.dump(self.config, default_flow_style=False))
        finally:
            config_file.close()

    def config_changed(self):
        """Makes sure that all tasks will have the config_modified flag come out true on the next run.
        Useful when changing the db and all tasks need to be completely reprocessed."""
        from flexget.task import config_changed
        for task in self.tasks:
            config_changed(task)

    def pre_check_config(self, config):
        """Checks configuration file for common mistakes that are easily detectable"""

        def get_indentation(line):
            i, n = 0, len(line)
            while i < n and line[i] == ' ':
                i += 1
            return i

        def isodd(n):
            return bool(n % 2)

        line_num = 0
        duplicates = {}
        # flags
        prev_indentation = 0
        prev_mapping = False
        prev_list = True
        prev_scalar = True
        list_open = False  # multiline list with [

        for line in config.splitlines():
            if '# warnings off' in line.strip().lower():
                log.debug('config pre-check warnings off')
                break
            line_num += 1
            # remove linefeed
            line = line.rstrip()
            # empty line
            if line.strip() == '':
                continue
            # comment line
            if line.strip().startswith('#'):
                continue
            indentation = get_indentation(line)

            if prev_scalar:
                if indentation <= prev_indentation:
                    prev_scalar = False
                else:
                    continue

            cur_list = line.strip().startswith('-')

            # skipping lines as long as multiline compact list is open
            if list_open:
                if line.strip().endswith(']'):
                    list_open = False
#                    print 'closed list at line %s' % line
                continue
            else:
                list_open = line.strip().endswith(': [') or line.strip().endswith(':[')
                if list_open:
#                    print 'list open at line %s' % line
                    continue

#            print '#%i: %s' % (line_num, line)
#            print 'indentation: %s, prev_ind: %s, prev_mapping: %s, prev_list: %s, cur_list: %s' % \
#                  (indentation, prev_indentation, prev_mapping, prev_list, cur_list)

            if ':\t' in line:
                log.critical('Line %s has TAB character after : character. '
                             'DO NOT use tab key when editing config!' % line_num)
            elif '\t' in line:
                log.warning('Line %s has tabs, use only spaces!' % line_num)
            if isodd(indentation):
                log.warning('Config line %s has odd (uneven) indentation' % line_num)
            if indentation > prev_indentation and not prev_mapping:
                # line increases indentation, but previous didn't start mapping
                log.warning('Config line %s is likely missing \':\' at the end' % (line_num - 1))
            if indentation > prev_indentation + 2 and prev_mapping and not prev_list:
                # mapping value after non list indented more than 2
                log.warning('Config line %s is indented too much' % line_num)
            if indentation <= prev_indentation + (2 * (not cur_list)) and prev_mapping and prev_list:
                log.warning('Config line %s is not indented enough' % line_num)
            if prev_mapping and cur_list:
                # list after opening mapping
                if indentation < prev_indentation or indentation > prev_indentation + 2 + (2 * prev_list):
                    log.warning('Config line %s containing list element is indented incorrectly' % line_num)
            elif prev_mapping and indentation <= prev_indentation:
                # after opening a map, indentation doesn't increase
                log.warning('Config line %s is indented incorrectly (previous line ends with \':\')' % line_num)

            # notify if user is trying to set same key multiple times in a task (a common mistake)
            for level in duplicates.iterkeys():
                # when indentation goes down, delete everything indented more than that
                if indentation < level:
                    duplicates[level] = {}
            if ':' in line:
                name = line.split(':', 1)[0].strip()
                ns = duplicates.setdefault(indentation, {})
                if name in ns:
                    log.warning('Trying to set value for `%s` in line %s, but it is already defined in line %s!' %
                        (name, line_num, ns[name]))
                ns[name] = line_num

            prev_indentation = indentation
            # this line is a mapping (ends with :)
            prev_mapping = line[-1] == ':'
            prev_scalar = line[-1] in '|>'
            # this line is a list
            prev_list = line.strip()[0] == '-'
            if prev_list:
                # This line is in a list, so clear the duplicates,
                # as duplicates are not always wrong in a list. see #697
                duplicates[indentation] = {}

        log.debug('Pre-checked %s configuration lines' % line_num)

    def validate_config(self):
        """
        Check all root level keywords are valid.

        :returns: A list of `ValidationError`s
        """
        return config_schema.process_config(self.config)

    def init_sqlalchemy(self):
        """Initialize SQLAlchemy"""
        try:
            if [int(part) for part in sqlalchemy.__version__.split('.')] < [0, 7, 0]:
                print('FATAL: SQLAlchemy 0.7.0 or newer required. Please upgrade your SQLAlchemy.', file=sys.stderr)
                sys.exit(1)
        except ValueError as e:
            log.critical('Failed to check SQLAlchemy version, you may need to upgrade it')

        # SQLAlchemy
        if self.database_uri is None:
            self.db_filename = os.path.join(self.config_base, 'db-%s.sqlite' % self.config_name)
            if self.options.test:
                db_test_filename = os.path.join(self.config_base, 'test-%s.sqlite' % self.config_name)
                log.info('Test mode, creating a copy from database ...')
                if os.path.exists(self.db_filename):
                    shutil.copy(self.db_filename, db_test_filename)
                self.db_filename = db_test_filename
                log.info('Test database created')

            # in case running on windows, needs double \\
            filename = self.db_filename.replace('\\', '\\\\')
            self.database_uri = 'sqlite:///%s' % filename

        if self.db_filename and not os.path.exists(self.db_filename):
            log.verbose('Creating new database %s ...' % self.db_filename)

        # fire up the engine
        log.debug('Connecting to: %s' % self.database_uri)
        try:
            self.engine = sqlalchemy.create_engine(self.database_uri,
                                                   echo=self.options.debug_sql,
                                                   poolclass=SingletonThreadPool,
                                                   connect_args={'check_same_thread': False})  # assert_unicode=True
        except ImportError:
            print('FATAL: Unable to use SQLite. Are you running Python 2.5 - 2.7 ?\n'
                  'Python should normally have SQLite support built in.\n'
                  'If you\'re running correct version of Python then it is not equipped with SQLite.\n'
                  'You can try installing `pysqlite`. If you have compiled python yourself, '
                  'recompile it with SQLite support.', file=sys.stderr)
            sys.exit(1)
        Session.configure(bind=self.engine)
        # create all tables, doesn't do anything to existing tables
        try:
            def before_table_create(event, target, bind, tables=None, **kw):
                if tables:
                    # We need to acquire a lock if we are creating new tables
                    # TODO: Detect if any database upgrading is needed and acquire the lock only in one place
                    self.acquire_lock(event=False).__enter__()

            Base.metadata.append_ddl_listener('before-create', before_table_create)
            Base.metadata.create_all(bind=self.engine)
        except OperationalError as e:
            if os.path.exists(self.db_filename):
                print('%s - make sure you have write permissions to file %s' %
                      (e.message, self.db_filename), file=sys.stderr)
            else:
                print('%s - make sure you have write permissions to directory %s' %
                      (e.message, self.config_base), file=sys.stderr)
            raise Exception(e.message)

    def _read_lock(self):
        """
        Read the values from the lock file. Returns None if there is no current lock file.
        """
        if self.lockfile and os.path.exists(self.lockfile):
            result = {}
            with open(self.lockfile) as f:
                lines = [l for l in f.readlines() if l]
            for line in lines:
                key, value = line.split(b':', 1)
                result[key.strip().lower()] = value.strip()
            for key in result:
                if result[key].isdigit():
                    result[key] = int(result[key])
            if not pid_exists(result['pid']):
                return None
            return result
        return None

    def check_lock(self):
        """Returns True if there is a lock on the database."""
        lock_info = self._read_lock()
        if not lock_info:
            return False
        # Don't count it if we hold the lock
        if os.getpid() == lock_info['pid']:
            return False
        return True

    def check_ipc_info(self):
        """If a daemon has a lock on the database, return info to connect to IPC."""
        lock_info = self._read_lock()
        if lock_info and 'port' in lock_info:
            return lock_info
        return None

    @contextmanager
    def acquire_lock(self, event=True):
        """
        :param bool event: If True, the 'manager.lock-acquired' event will be fired after a lock is obtained
        """
        acquired = False
        try:
            # Don't do anything if we already have a lock. This means only the outermost call will release the lock file
            if not self._has_lock:
                # Exit if there is an existing lock.
                if self.check_lock():
                    with open(self.lockfile) as f:
                        pid = f.read()
                    print('Another process (%s) is running, will exit.' % pid.split('\n')[0], file=sys.stderr)
                    print('If you\'re sure there is no other instance running, delete %s' % self.lockfile,
                          file=sys.stderr)
                    sys.exit(1)

                self._has_lock = True
                self.write_lock()
                acquired = True
                if event:
                    fire_event('manager.lock-acquired', self)
            yield
        finally:
            if acquired:
                self.release_lock()
                self._has_lock = False

    def write_lock(self, ipc_info=None):
        assert self._has_lock
        with open(self.lockfile, 'w') as f:
            f.write(b'PID: %s\n' % os.getpid())
            if ipc_info:
                for key in sorted(ipc_info):
                    f.write(b'%s: %s\n' % (key, ipc_info[key]))

    def release_lock(self):
        if os.path.exists(self.lockfile):
            os.remove(self.lockfile)
            log.debug('Removed %s' % self.lockfile)
        else:
            log.debug('Lockfile %s not found' % self.lockfile)

    def daemonize(self):
        """Daemonizes the current process. Returns the new pid"""
        if sys.platform.startswith('win'):
            log.error('Cannot daemonize on windows')
            return
        if threading.activeCount() != 1:
            log.critical('There are %r active threads. '
                         'Daemonizing now may cause strange failures.' % threading.enumerate())

        log.info('Daemonizing...')

        try:
            pid = os.fork()
            if pid > 0:
                # Don't run the exit handlers on the parent
                atexit._exithandlers = []
                # exit first parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write('fork #1 failed: %d (%s)\n' % (e.errno, e.strerror))
            sys.exit(1)

        # decouple from parent environment
        os.chdir('/')
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Don't run the exit handlers on the parent
                atexit._exithandlers = []
                # exit from second parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write('fork #2 failed: %d (%s)\n' % (e.errno, e.strerror))
            sys.exit(1)

        log.info('Daemonize complete. New PID: %s' % os.getpid())
        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = file('/dev/null', 'r')
        so = file('/dev/null', 'a+')
        se = file('/dev/null', 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

    def db_cleanup(self, force=False):
        """
        Perform database cleanup if cleanup interval has been met.

        Fires events:

        * manager.db_cleanup

          If interval was met. Gives session to do the cleanup as a parameter.

        :param bool force: Run the cleanup no matter whether the interval has been met.
        """
        expired = self.persist.get('last_cleanup', datetime(1900, 1, 1)) < datetime.now() - DB_CLEANUP_INTERVAL
        if force or expired:
            log.info('Running database cleanup.')
            session = Session()
            try:
                fire_event('manager.db_cleanup', session)
                session.commit()
            finally:
                session.close()
            # Just in case some plugin was overzealous in its cleaning, mark the config changed
            self.config_changed()
            self.persist['last_cleanup'] = datetime.now()
        else:
            log.debug('Not running db cleanup, last run %s' % self.persist.get('last_cleanup'))

    def shutdown(self, finish_queue=True):
        """
        Application is being exited

        :param bool finish_queue: Should scheduler finish the task queue
        """
        # Wait for scheduler to finish
        self.scheduler.shutdown(finish_queue=finish_queue)
        try:
            self.scheduler.wait()
        except KeyboardInterrupt:
            log.debug('Not waiting for scheduler shutdown due to ctrl-c')
            # show real stack trace in debug mode
            if manager.options.debug:
                raise
            print('**** Keyboard Interrupt ****')
        fire_event('manager.shutdown', self)
        if not self.unit_test:  # don't scroll "nosetests" summary results when logging is enabled
            log.debug('Shutting down')
        self.engine.dispose()
        # remove temporary database used in test mode
        if self.options.test:
            if not 'test' in self.db_filename:
                raise Exception('trying to delete non test database?')
            if self._has_lock:
                os.remove(self.db_filename)
                log.info('Removed test database')
        if not self.unit_test:  # don't scroll "nosetests" summary results when logging is enabled
            log.debug('Shutdown completed')
