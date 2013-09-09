from __future__ import unicode_literals, division, absolute_import
import os
import sys
import shutil
import logging
import yaml
import codecs
import atexit
from datetime import datetime, timedelta

import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import SingletonThreadPool

from flexget.event import fire_event
from flexget import config_schema

log = logging.getLogger('manager')

Base = declarative_base()
Session = sessionmaker()
manager = None
DB_CLEANUP_INTERVAL = timedelta(days=7)

# Validator that handles root structure of config.
_root_config_schema = {'type': 'object', 'additionalProperties': False}
# TODO: Is /schema/root this the best place for this?
config_schema.register_schema('/schema/root', _root_config_schema)


def register_config_key(key, schema, required=False):
    """ Registers a valid root level key for the config.

    :param string key:
      Name of the root level key being registered.
    :param dict schema:
      Schema for the key.
    :param bool required:
      Specify whether this is a mandatory key.
    """
    _root_config_schema.setdefault('properties', {})[key] = schema
    if required:
        _root_config_schema.setdefault('required', []).append(key)


def useExecLogging(func):
    """
    Decorator for setting task name to log messages.
    """

    def wrapper(self, *args, **kw):
        # Set the task name in the logger
        from flexget import logger
        import time
        logger.set_execution(str(time.time()))
        try:
            return func(self, *args, **kw)
        finally:
            logger.set_execution('')

    return wrapper


class Manager(object):

    """Manager class for FlexGet

    Fires events:

    * manager.startup

      After manager has been initialized. This is when application becomes ready to use

    * manager.upgrade

      Upgrade plugin database schemas etc

    * manager.execute.started

      When execute is about the be started, this happens before any task phases occur
      including on_process_start

    * manager.execute.completed

      After manager has executed all Tasks

    * manager.shutdown

      When the manager is exiting
    """

    unit_test = False
    options = None

    def __init__(self, options):
        """
        :param options: argparse parsed options object
        """
        global manager
        assert not manager, 'Only one instance of Manager should be created at a time!'
        manager = self
        self.options = options
        self.config_base = None
        self.config_name = None
        self.db_filename = None
        self.engine = None
        self.lockfile = None
        self.database_uri = None
        self.db_upgraded = False

        self.config = {}
        self.tasks = {}

        self.initialize()

        # check if stdout is not connected to terminal (cron run)
        #if not os.isatty(sys.stdout.fileno()):
        #    log.warning('It appears you\'re running from CRON')
        #else:
        #    log.warning('It appears you\'re running from terminal')

        # cannot be imported at module level because of circular references
        from flexget.utils.simple_persistence import SimplePersistence
        self.persist = SimplePersistence('manager')

        log.debug('sys.defaultencoding: %s' % sys.getdefaultencoding())
        log.debug('sys.getfilesystemencoding: %s' % sys.getfilesystemencoding())
        log.debug('os.path.supports_unicode_filenames: %s' % os.path.supports_unicode_filenames)

        fire_event('manager.upgrade', self)
        if manager.db_upgraded:
            fire_event('manager.db_upgraded', self)
        fire_event('manager.startup', self)
        self.db_cleanup()

    def __del__(self):
        global manager
        manager = None

    def initialize(self):
        """Separated from __init__ so that unit tests can modify options before loading config."""
        self.setup_yaml()
        self.find_config()
        self.acquire_lock()
        self.init_sqlalchemy()
        errors = self.validate_config()
        if errors:
            for error in errors:
                log.critical("[%s] %s", error.json_pointer, error.message)
            return
        self.create_tasks()

    def setup_yaml(self):
        """ Set up the yaml loader to return unicode objects for strings by default
        """

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

    def find_config(self):
        """Find the configuration file and then call :meth:`.load_config` to load it"""
        startup_path = os.path.dirname(os.path.abspath(sys.path[0]))
        home_path = os.path.join(os.path.expanduser('~'), '.flexget')
        current_path = os.getcwd()
        exec_path = sys.path[0]

        config_path = os.path.dirname(self.options.config)
        path_given = config_path != ''

        possible = []
        if path_given:
            # explicit path given, don't try anything too fancy
            possible.append(self.options.config)
        else:
            log.debug('Figuring out config load paths')
            # normal lookup locations
            possible.append(startup_path)
            possible.append(home_path)
            if sys.platform.startswith('win'):
                # On windows look in ~/flexget as well, as explorer does not let you create a folder starting with a dot
                possible.append(os.path.join(os.path.expanduser('~'), 'flexget'))
            else:
                # The freedesktop.org standard config location
                xdg_config = os.environ.get('XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config'))
                possible.append(os.path.join(xdg_config, 'flexget'))
            # for virtualenv / dev sandbox
            from flexget import __version__ as version
            if version == '{git}':
                log.debug('Running git, adding virtualenv / sandbox paths')
                possible.append(os.path.join(exec_path, '..'))
                possible.append(current_path)
                possible.append(exec_path)

        for path in possible:
            config = os.path.join(path, self.options.config)
            if os.path.exists(config):
                log.debug('Found config: %s' % config)
                self.load_config(config)
                return
        log.info('Tried to read from: %s' % ', '.join(possible))
        raise IOError('Failed to find configuration file %s' % self.options.config)

    def load_config(self, config_path):
        """
        .. warning::

           Calls sys.exit(1) if configuration file could not be loaded.
           This is something we probably want to change.

        :param string config_path: Path to configuration file
        """
        with open(config_path, 'rb') as file:
            config = file.read()
        try:
            config = config.decode('utf-8')
        except UnicodeDecodeError:
            log.critical('Config file must be UTF-8 encoded.')
            sys.exit(1)
        if not self.options.quiet:
            # pre-check only when running without --cron
            self.pre_check_config(config)
        try:
            self.config = yaml.safe_load(config) or {}
        except Exception as e:
            msg = str(e).replace('\n', ' ')
            msg = ' '.join(msg.split())
            log.critical(msg)
            print ''
            print '-' * 79
            print ' Malformed configuration file (check messages above). Common reasons:'
            print '-' * 79
            print ''
            print ' o Indentation error'
            print ' o Missing : from end of the line'
            print ' o Non ASCII characters (use UTF8)'
            print ' o If text contains any of :[]{}% characters it must be single-quoted ' \
                  '(eg. value{1} should be \'value{1}\')\n'

            # Not very good practice but we get several kind of exceptions here, I'm not even sure all of them
            # At least: ReaderError, YmlScannerError (or something like that)
            if hasattr(e, 'problem') and hasattr(e, 'context_mark') and hasattr(e, 'problem_mark'):
                lines = 0
                if e.problem is not None:
                    print ' Reason: %s\n' % e.problem
                    if e.problem == 'mapping values are not allowed here':
                        print ' ----> MOST LIKELY REASON: Missing : from end of the line!'
                        print ''
                if e.context_mark is not None:
                    print ' Check configuration near line %s, column %s' % (e.context_mark.line, e.context_mark.column)
                    lines += 1
                if e.problem_mark is not None:
                    print ' Check configuration near line %s, column %s' % (e.problem_mark.line, e.problem_mark.column)
                    lines += 1
                if lines:
                    print ''
                if lines == 1:
                    print ' Fault is almost always in this or previous line\n'
                if lines == 2:
                    print ' Fault is almost always in one of these lines or previous ones\n'

            # When --debug escalate to full stacktrace
            if self.options.debug:
                raise
            sys.exit(1)

        # config loaded successfully
        self.config_name = os.path.splitext(os.path.basename(config_path))[0]
        self.config_base = os.path.normpath(os.path.dirname(config_path))
        self.lockfile = os.path.join(self.config_base, '.%s-lock' % self.config_name)
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
        for task in self.tasks.values():
            task.config_changed()

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
        return config_schema.process_config(self.config, _root_config_schema)

    def init_sqlalchemy(self):
        """Initialize SQLAlchemy"""
        try:
            if [int(part) for part in sqlalchemy.__version__.split('.')] < [0, 7, 0]:
                print >> sys.stderr, 'FATAL: SQLAlchemy 0.7.0 or newer required. Please upgrade your SQLAlchemy.'
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
                                                   )  # assert_unicode=True
        except ImportError:
            print >> sys.stderr, ('FATAL: Unable to use SQLite. Are you running Python 2.5 - 2.7 ?\n'
                                  'Python should normally have SQLite support built in.\n'
                                  'If you\'re running correct version of Python then it is not equipped with SQLite.\n'
                                  'You can try installing `pysqlite`. If you have compiled python yourself, '
                                  'recompile it with SQLite support.')
            sys.exit(1)
        Session.configure(bind=self.engine)
        # create all tables, doesn't do anything to existing tables
        from sqlalchemy.exc import OperationalError
        try:
            if self.options.reset or self.options.del_db:
                log.verbose('Deleting everything from database ...')
                Base.metadata.drop_all(bind=self.engine)
            Base.metadata.create_all(bind=self.engine)
        except OperationalError as e:
            if os.path.exists(self.db_filename):
                print >> sys.stderr, '%s - make sure you have write permissions to file %s' % \
                                     (e.message, self.db_filename)
            else:
                print >> sys.stderr, '%s - make sure you have write permissions to directory %s' % \
                                     (e.message, self.config_base)
            raise Exception(e.message)

    def check_lock(self):
        """Checks if there is already a lock, returns True if there is."""
        if os.path.exists(self.lockfile):
            # check the lock age
            lock_time = datetime.fromtimestamp(os.path.getmtime(self.lockfile))
            if (datetime.now() - lock_time).seconds > 36000:
                log.warning('Lock file over 10 hour in age, ignoring it ...')
            else:
                return True
        return False

    def acquire_lock(self):
        if self.options.log_start:
            log.info('FlexGet started (PID: %s)' % os.getpid())

        # Exit if there is an existing lock.
        if self.check_lock():
            if not self.options.quiet:
                f = file(self.lockfile)
                pid = f.read()
                f.close()
                print >> sys.stderr, 'Another process (%s) is running, will exit.' % pid.strip()
                print >> sys.stderr, 'If you\'re sure there is no other instance running, delete %s' % self.lockfile
            sys.exit(1)

        f = file(self.lockfile, 'w')
        f.write('PID: %s\n' % os.getpid())
        f.close()
        atexit.register(self.release_lock)

    def release_lock(self):
        if self.options.log_start:
            log.info('FlexGet stopped (PID: %s)' % os.getpid())
        if os.path.exists(self.lockfile):
            os.remove(self.lockfile)
            log.debug('Removed %s' % self.lockfile)
        else:
            log.debug('Lockfile %s not found' % self.lockfile)

    def create_tasks(self):
        """Creates instances of all configured tasks"""
        from flexget.task import Task
        # Clear tasks dict
        self.tasks = {}

        # Backwards compatibility with feeds key
        if 'feeds' in self.config:
            log.warning('`feeds` key has been deprecated and replaced by `tasks`. Please update your config.')
            if 'tasks' in self.config:
                log.error('You have defined both `feeds` and `tasks`. Stop that.')
            self.config['tasks'] = self.config.pop('feeds')
        # construct task list
        tasks = self.config.get('tasks', {}).keys()
        for name in tasks:
            # Make sure numeric task names are turned into strings. #1763, #1961
            if not isinstance(name, basestring):
                self.config['tasks'][unicode(name)] = self.config['tasks'].pop(name)
                name = unicode(name)
            # create task
            task = Task(self, name, self.config['tasks'][name])
            # if task name is prefixed with _ it's disabled
            if name.startswith('_'):
                task.enabled = False
            self.tasks[name] = task

    def disable_tasks(self):
        """Disables all tasks."""
        for task in self.tasks.itervalues():
            task.enabled = False

    def enable_tasks(self):
        """Enables all tasks."""
        for task in self.tasks.itervalues():
            task.enabled = True

    def process_start(self, tasks=None):
        """Execute process_start for tasks.

        :param list tasks: Optional list of :class:`~flexget.task.Task` instances, defaults to all.
        """
        if tasks is None:
            tasks = self.tasks.values()

        for task in tasks:
            if not task.enabled:
                continue
            try:
                log.trace('calling process_start on a task %s' % task.name)
                task._process_start()
            except Exception as e:
                task.enabled = False
                log.exception('Task %s process_start: %s' % (task.name, e))

    def process_end(self, tasks=None):
        """Execute process_end for all tasks.

        :param list tasks: Optional list of :class:`~flexget.task.Task` instances, defaults to all.
        """
        if tasks is None:
            tasks = self.tasks.values()

        for task in tasks:
            if not task.enabled:
                continue
            if task._abort:
                continue
            try:
                log.trace('calling process_end on a task %s' % task.name)
                task._process_end()
            except Exception as e:
                log.exception('Task %s process_end: %s' % (task.name, e))

    @useExecLogging
    def execute(self, tasks=None, disable_phases=None, entries=None):
        """
        Iterate trough tasks and run them. If --learn is used download and output
        phases are disabled.

        :param list tasks: Optional list of task names to run, all tasks otherwise.
        :param list disable_phases: Optional list of phases to disabled
        :param list entries: Optional list of entries to pass into task(s).
            This will also cause task to disable input phase.
        """
        # Make a list of Task instances to execute
        if tasks is None:
            # Default to all tasks if none are specified
            run_tasks = self.tasks.values()
        else:
            # Turn the list of task names or instances into a list of instances
            run_tasks = []
            for task in tasks:
                if isinstance(task, basestring):
                    if task in self.tasks:
                        run_tasks.append(self.tasks[task])
                    else:
                        log.error('Task `%s` does not exist.' % task)
                else:
                    run_tasks.append(task)

        if not run_tasks:
            log.warning('There are no tasks to execute, please add some tasks')
            return

        disable_phases = disable_phases or []
        # when learning, skip few phases
        if self.options.learn:
            log.info('Disabling download and output phases because of %s' %
                     ('--reset' if self.options.reset else '--learn'))
            disable_phases.extend(['download', 'output'])

        fire_event('manager.execute.started', self)
        self.process_start(tasks=run_tasks)

        for task in sorted(run_tasks):
            if not task.enabled or task._abort:
                continue
            try:
                task.execute(disable_phases=disable_phases, entries=entries)
            except Exception as e:
                task.enabled = False
                log.exception('Task %s: %s' % (task.name, e))
            except KeyboardInterrupt:
                # show real stack trace in debug mode
                if self.options.debug:
                    raise
                print '**** Keyboard Interrupt ****'
                return

        self.process_end(tasks=run_tasks)
        fire_event('manager.execute.completed', self)

    def db_cleanup(self):
        """ Perform database cleanup if cleanup interval has been met.
        """
        expired = self.persist.get('last_cleanup', datetime.now()) < datetime.now() - DB_CLEANUP_INTERVAL
        if self.options.db_cleanup or not self.persist.get('last_cleanup') or expired and \
                any([t.enabled for t in self.tasks.values()]):
            if not self.options.db_cleanup and not self.options.quiet:
                log.verbose('Not running database cleanup on manual run. It will be run on next --cron run.')
                return
            log.info('Running database cleanup.')
            session = Session()
            fire_event('manager.db_cleanup', session)
            session.commit()
            session.close()
            # Just in case some plugin was overzealous in its cleaning, mark the config changed
            self.config_changed()
            self.persist['last_cleanup'] = datetime.now()
        else:
            log.debug('Not running db cleanup, last run %s' % self.persist.get('last_cleanup'))

    def shutdown(self):
        """ Application is being exited
        """
        fire_event('manager.shutdown', self)
        if not self.unit_test:  # don't scroll "nosetests" summary results when logging is enabled
            log.debug('Shutting down')
        self.engine.dispose()
        # remove temporary database used in test mode
        if self.options.test:
            if not 'test' in self.db_filename:
                raise Exception('trying to delete non test database?')
            os.remove(self.db_filename)
            log.info('Removed test database')
        if not self.unit_test:  # don't scroll "nosetests" summary results when logging is enabled
            log.debug('Shutdown completed')
