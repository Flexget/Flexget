from __future__ import unicode_literals, division, absolute_import, print_function

# This needs to remain before the builtins import!
native_int = int

from builtins import *  # noqa  pylint: disable=unused-import, redefined-builtin

import atexit  # noqa
import codecs  # noqa
import copy  # noqa
import fnmatch  # noqa
import logging  # noqa
import os  # noqa
import shutil  # noqa
import signal  # noqa
import sys  # noqa
import threading  # noqa
import traceback  # noqa
import hashlib  # noqa
from contextlib import contextmanager  # noqa
from datetime import datetime, timedelta  # noqa
import io  # noqa

import sqlalchemy  # noqa
import yaml  # noqa
from sqlalchemy.exc import OperationalError  # noqa
from sqlalchemy.ext.declarative import declarative_base  # noqa
from sqlalchemy.orm import sessionmaker  # noqa

# These need to be declared before we start importing from other flexget modules, since they might import them
from flexget.utils.sqlalchemy_utils import ContextSession  # noqa

Base = declarative_base()
Session = sessionmaker(class_=ContextSession)

from flexget import config_schema, db_schema, logger, plugin  # noqa
from flexget.event import fire_event  # noqa
from flexget.ipc import IPCClient, IPCServer  # noqa
from flexget.options import CoreArgumentParser, get_parser, manager_parser, ParserError, unicode_argv  # noqa
from flexget.task import Task  # noqa
from flexget.task_queue import TaskQueue  # noqa
from flexget.utils.tools import pid_exists, get_current_flexget_version, io_encoding  # noqa
from flexget.terminal import console  # noqa

log = logging.getLogger('manager')

manager = None
DB_CLEANUP_INTERVAL = timedelta(days=7)


class Manager(object):
    """Manager class for FlexGet

    Fires events:

    * manager.initialize

      The first time the manager is initialized, before config is loaded

    * manager.before_config_load

      Before the config file is loaded from disk

    * manager.before_config_validate

      When updating the config, before the validator is run on it

    * manager.config_updated

      After a configuration file has been loaded or changed (and validated) this event is fired

    * manager.startup

      After manager has been initialized. This is when application becomes ready to use, however no database lock is
      present, so the database must not be modified on this event.

    * manager.lock_acquired

      The manager does not always require a lock on startup, if one is requested, this event will run when it has been
      acquired successfully

    * manager.upgrade

      If any plugins have declared a newer schema version than exists in the database, this event will be fired to
      allow plugins to upgrade their tables

    * manager.shutdown_requested

      When shutdown has been requested. Any plugins which might add to execution queue should stop when this is fired.

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

    def __init__(self, args):
        """
        :param args: CLI args
        """
        global manager
        if not self.unit_test:
            assert not manager, 'Only one instance of Manager should be created at a time!'
        elif manager:
            log.info('last manager was not torn down correctly')

        if args is None:
            # Decode all arguments to unicode before parsing
            args = unicode_argv()[1:]
        self.args = args
        self.autoreload_config = False
        self.config_file_hash = None
        self.config_base = None
        self.config_name = None
        self.config_path = None
        self.db_filename = None
        self.engine = None
        self.lockfile = None
        self.database_uri = None
        self.db_upgraded = False
        self._has_lock = False
        self.is_daemon = False
        self.ipc_server = None
        self.task_queue = None
        self.persist = None
        self.initialized = False

        self.config = {}

        self.options = self._init_options(args)
        try:
            self._init_config(create=False)
        except:
            logger.start(level=self.options.loglevel.upper(), to_file=False)
            raise
        else:
            self._init_logging()

        manager = self

        log.debug('sys.defaultencoding: %s', sys.getdefaultencoding())
        log.debug('sys.getfilesystemencoding: %s', sys.getfilesystemencoding())
        log.debug('flexget detected io encoding: %s', io_encoding)
        log.debug('os.path.supports_unicode_filenames: %s' % os.path.supports_unicode_filenames)
        if codecs.lookup(sys.getfilesystemencoding()).name == 'ascii' and not os.path.supports_unicode_filenames:
            log.warning('Your locale declares ascii as the filesystem encoding. Any plugins reading filenames from '
                        'disk will not work properly for filenames containing non-ascii characters. Make sure your '
                        'locale env variables are set up correctly for the environment which is launching FlexGet.')

    def _init_options(self, args):
        """
        Initialize argument parsing
        """
        if '--help' in args or '-h' in args:
            # TODO: This is a bit hacky, but we can't call parse on real arguments when --help is used because it will
            # cause a system exit before plugins are loaded and print incomplete help. This will get us a default
            # options object and we'll parse the real args later, or send them to daemon. #2807
            # TODO: this will cause command failure in case of config.yml does not
            # exists and user runs "flexget -c some.yml --help"
            options = CoreArgumentParser().parse_known_args(['execute'])[0]
        else:
            try:
                options = CoreArgumentParser().parse_known_args(args)[0]
            except ParserError:
                try:
                    # If a non-built-in command was used, we need to parse with a parser that
                    # doesn't define the subparsers
                    options = manager_parser.parse_known_args(args)[0]
                except ParserError as e:
                    manager_parser.print_help()
                    print('\nError: %s' % e.message)
                    sys.exit(1)
        try:
            if options.cli_command is None:
                # TODO: another hack ...
                # simply running "flexget -c config.yml" fails, let's fix that
                manager_parser.print_help()
                print('\nCommand missing, eg. execute or daemon ...')
                # TODO: oh dear ...
                if '--help' in args or '-h' in args:
                    print('NOTE: The help may be incomplete due issues with argparse. Try without --help.')
                else:
                    print('NOTE: The help may be incomplete due issues with argparse. Try with --help.')
                sys.exit(1)
        except AttributeError:
            pass  # TODO: hack .. this is getting out of hand
        return options


    def _init_logging(self):
        """
        Initialize logging facilities
        """
        log_file = os.path.expanduser(self.options.logfile)
        # If an absolute path is not specified, use the config directory.
        if not os.path.isabs(log_file):
            log_file = os.path.join(self.config_base, log_file)
        logger.start(log_file, self.options.loglevel.upper(), to_console=not self.options.cron)

    def initialize(self):
        """
        Load plugins, database, and config. Also initializes (but does not start) the task queue and ipc server.
        This should only be called after obtaining a lock.
        """
        if self.initialized:
            raise RuntimeError('Cannot call initialize on an already initialized manager.')

        plugin.load_plugins(extra_dirs=[os.path.join(self.config_base, 'plugins')])

        # Reparse CLI options now that plugins are loaded
        if not self.args:
            self.args = ['--help']
        self.options = get_parser().parse_args(self.args)

        self.task_queue = TaskQueue()
        self.ipc_server = IPCServer(self, self.options.ipc_port)

        self.setup_yaml()
        self.init_sqlalchemy()
        fire_event('manager.initialize', self)
        try:
            self.load_config()
        except ValueError as e:
            log.critical('Failed to load config file: %s' % e.args[0])
            raise

        # cannot be imported at module level because of circular references
        from flexget.utils.simple_persistence import SimplePersistence
        self.persist = SimplePersistence('manager')

        if db_schema.upgrade_required():
            log.info('Database upgrade is required. Attempting now.')
            fire_event('manager.upgrade', self)
            if manager.db_upgraded:
                fire_event('manager.db_upgraded', self)
        fire_event('manager.startup', self)
        self.initialized = True

    @property
    def tasks(self):
        """A list of tasks in the config"""
        if not self.config:
            return []
        return list(self.config.get('tasks', {}).keys())

    @property
    def has_lock(self):
        return self._has_lock

    def execute(self, options=None, output=None, loglevel=None, priority=1, suppress_warnings=None):
        """
        Run all (can be limited with options) tasks from the config.

        :param options: Either an :class:`argparse.Namespace` instance, or a dict, containing options for execution
        :param output: If a file-like object is specified here, log messages and stdout from the execution will be
            written to it.
        :param priority: If there are other executions waiting to be run, they will be run in priority order,
            lowest first.
        :param suppress_warnings: Allows suppressing log warning about missing plugin in key phases
        :returns: a list of :class:`threading.Event` instances which will be
            set when each respective task has finished running
        """
        if options is None:
            options = copy.copy(self.options.execute)
        elif isinstance(options, dict):
            options_namespace = copy.copy(self.options.execute)
            options_namespace.__dict__.update(options)
            options = options_namespace
        task_names = self.tasks
        # Only reload config if daemon
        config_hash = self.hash_config()
        if self.is_daemon and self.autoreload_config and self.config_file_hash != config_hash:
            log.info('Config change detected. Reloading.')
            try:
                self.load_config(output_to_console=False, config_file_hash=config_hash)
                log.info('Config successfully reloaded!')
            except Exception as e:
                log.error('Reloading config failed: %s', e)
        # Handle --tasks
        if options.tasks:
            # Consider * the same as not specifying tasks at all (makes sure manual plugin still works)
            if options.tasks == ['*']:
                options.tasks = None
            else:
                # Create list of tasks to run, preserving order
                task_names = []
                for arg in options.tasks:
                    matches = [t for t in self.tasks if fnmatch.fnmatchcase(str(t).lower(), arg.lower())]
                    if not matches:
                        msg = '`%s` does not match any tasks' % arg
                        log.error(msg)
                        if output:
                            output.write(msg)
                        continue
                    task_names.extend(m for m in matches if m not in task_names)
                # Set the option as a list of matching task names so plugins can use it easily
                options.tasks = task_names
        # TODO: 1.2 This is a hack to make task priorities work still, not sure if it's the best one
        task_names = sorted(task_names, key=lambda t: self.config['tasks'][t].get('priority', 65535))

        finished_events = []
        for task_name in task_names:
            task = Task(
                self, task_name, options=options, output=output,
                loglevel=loglevel, priority=priority, suppress_warnings=suppress_warnings
            )
            self.task_queue.put(task)
            finished_events.append((task.id, task.name, task.finished_event))
        return finished_events

    def start(self):
        """
        Starting point when executing from commandline, dispatch execution to correct destination.

        If there is a FlexGet process with an ipc server already running, the command will be sent there for execution
        and results will be streamed back.
        If not, this will attempt to obtain a lock, initialize the manager, and run the command here.
        """
        # When we are in test mode, we use a different lock file and db
        if self.options.test:
            self.lockfile = os.path.join(self.config_base, '.test-%s-lock' % self.config_name)
        # If another process is started, send the execution to the running process
        ipc_info = self.check_ipc_info()
        if ipc_info:
            console('There is a FlexGet process already running for this config, sending execution there.')
            log.debug('Sending command to running FlexGet process: %s' % self.args)
            try:
                client = IPCClient(ipc_info['port'], ipc_info['password'])
            except ValueError as e:
                log.error(e)
            else:
                try:
                    client.handle_cli(self.args)
                except KeyboardInterrupt:
                    log.error('Disconnecting from daemon due to ctrl-c. Executions will still continue in the '
                              'background.')
                except EOFError:
                    log.error('Connection from daemon was severed.')
            return
        if self.options.test:
            log.info('Test mode, creating a copy from database ...')
            db_test_filename = os.path.join(self.config_base, 'test-%s.sqlite' % self.config_name)
            if os.path.exists(self.db_filename):
                shutil.copy(self.db_filename, db_test_filename)
                log.info('Test database created')
            self.db_filename = db_test_filename
        # No running process, we start our own to handle command
        with self.acquire_lock():
            self.initialize()
            self.handle_cli()
            self._shutdown()

    def handle_cli(self, options=None):
        """
        Dispatch a cli command to the appropriate function.

        * :meth:`.execute_command`
        * :meth:`.daemon_command`
        * CLI plugin callback function

        The manager should have a lock and be initialized before calling this method.

        :param options: argparse options for command. Defaults to options that manager was instantiated with.
        """
        if not options:
            options = self.options
        command = options.cli_command
        if command is None:
            raise Exception('Command missing')
        command_options = getattr(options, command)
        # First check for built-in commands
        if command in ['execute', 'daemon']:
            if command == 'execute':
                self.execute_command(command_options)
            elif command == 'daemon':
                self.daemon_command(command_options)
        else:
            # Otherwise dispatch the command to the callback function
            options.cli_command_callback(self, command_options)

    def execute_command(self, options):
        """
        Handles the 'execute' CLI command.

        If there is already a task queue running in this process, adds the execution to the queue.
        If FlexGet is being invoked with this command, starts up a task queue and runs the execution.

        Fires events:

        * manager.execute.started
        * manager.execute.completed

        :param options: argparse options
        """
        fire_event('manager.execute.started', self, options)
        if self.task_queue.is_alive() or self.is_daemon:
            if not self.task_queue.is_alive():
                log.error('Task queue has died unexpectedly. Restarting it. Please open an issue on Github and include'
                          ' any previous error logs.')
                self.task_queue = TaskQueue()
                self.task_queue.start()
            if len(self.task_queue):
                log.verbose('There is a task already running, execution queued.')
            finished_events = self.execute(options, output=logger.get_capture_stream(),
                                           loglevel=logger.get_capture_loglevel())
            if not options.cron:
                # Wait until execution of all tasks has finished
                for _, _, event in finished_events:
                    event.wait()
        else:
            self.task_queue.start()
            self.ipc_server.start()
            self.execute(options)
            self.shutdown(finish_queue=True)
            self.task_queue.wait()
        fire_event('manager.execute.completed', self, options)

    def daemon_command(self, options):
        """
        Handles the 'daemon' CLI command.

        Fires events:

        * manager.daemon.started
        * manager.daemon.completed

        :param options: argparse options
        """

        # Import API so it can register to daemon.started event
        if options.action == 'start':
            if self.is_daemon:
                log.error('Daemon already running for this config.')
                return
            elif self.task_queue.is_alive():
                log.error('Non-daemon execution of FlexGet is running. Cannot start daemon until it is finished.')
                return
            if options.daemonize:
                self.daemonize()
            if options.autoreload_config:
                self.autoreload_config = True
            try:
                signal.signal(signal.SIGTERM, self._handle_sigterm)
            except ValueError as e:
                # If flexget is being called from another script, e.g. windows service helper, and we are not the
                # main thread, this error will occur.
                log.debug('Error registering sigterm handler: %s' % e)
            self.is_daemon = True
            fire_event('manager.daemon.started', self)
            self.task_queue.start()
            self.ipc_server.start()
            self.task_queue.wait()
            fire_event('manager.daemon.completed', self)
        elif options.action in ['stop', 'reload-config', 'status']:
            if not self.is_daemon:
                log.error('There does not appear to be a daemon running.')
                return
            if options.action == 'status':
                log.info('Daemon running. (PID: %s)' % os.getpid())
            elif options.action == 'stop':
                tasks = 'all queued tasks (if any) have' if options.wait else 'currently running task (if any) has'
                log.info('Daemon shutdown requested. Shutdown will commence when %s finished executing.' % tasks)
                self.shutdown(options.wait)
            elif options.action == 'reload-config':
                log.info('Reloading config from disk.')
                try:
                    self.load_config()
                except ValueError as e:
                    log.error('Error loading config: %s' % e.args[0])
                else:
                    log.info('Config successfully reloaded from disk.')

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

        yaml.add_representer(str, unicode_representer)

        # Set up the dumper to increase the indent for lists
        def increase_indent_wrapper(func):
            def increase_indent(self, flow=False, indentless=False):
                func(self, flow, False)

            return increase_indent

        yaml.Dumper.increase_indent = increase_indent_wrapper(yaml.Dumper.increase_indent)
        yaml.SafeDumper.increase_indent = increase_indent_wrapper(yaml.SafeDumper.increase_indent)

    def _init_config(self, create=False):
        """
        Find and load the configuration file.

        :param bool create: If a config file is not found, and create is True, one will be created in the home folder
        :raises: `IOError` when no config file could be found, and `create` is False.
        """
        home_path = os.path.join(os.path.expanduser('~'), '.flexget')
        options_config = os.path.expanduser(self.options.config)

        possible = []
        if os.path.isabs(options_config):
            # explicit path given, don't try anything
            config = options_config
            possible = [config]
        else:
            log.debug('Figuring out config load paths')
            try:
                possible.append(os.getcwd())
            except OSError:
                log.debug('current directory invalid, not searching for config there')
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

        if create and not (config and os.path.exists(config)):
            config = os.path.join(home_path, options_config)
            log.info('Config file %s not found. Creating new config %s' % (options_config, config))
            with open(config, 'w') as newconfig:
                # Write empty tasks to the config
                newconfig.write(yaml.dump({'tasks': {}}))
        elif not config:
            log.critical('Failed to find configuration file %s' % options_config)
            log.info('Tried to read from: %s' % ', '.join(possible))
            raise IOError('No configuration file found.')
        if not os.path.isfile(config):
            raise IOError('Config `%s` does not appear to be a file.' % config)

        log.debug('Config file %s selected' % config)
        self.config_path = config
        self.config_name = os.path.splitext(os.path.basename(config))[0]
        self.config_base = os.path.normpath(os.path.dirname(config))
        self.lockfile = os.path.join(self.config_base, '.%s-lock' % self.config_name)
        self.db_filename = os.path.join(self.config_base, 'db-%s.sqlite' % self.config_name)

    def hash_config(self):
        if not self.config_path:
            return
        sha1_hash = hashlib.sha1()
        with io.open(self.config_path, 'rb') as f:
            while True:
                data = f.read(65536)
                if not data:
                    break
                sha1_hash.update(data)
        return sha1_hash.hexdigest()

    def load_config(self, output_to_console=True, config_file_hash=None):
        """
        Loads the config file from disk, validates and activates it.

        :raises: `ValueError` if there is a problem loading the config file
        """
        fire_event('manager.before_config_load', self)
        with io.open(self.config_path, 'r', encoding='utf-8') as f:
            try:
                raw_config = f.read()
            except UnicodeDecodeError:
                log.critical('Config file must be UTF-8 encoded.')
                raise ValueError('Config file is not UTF-8 encoded')
        try:
            self.config_file_hash = config_file_hash or self.hash_config()
            config = yaml.safe_load(raw_config) or {}
        except Exception as e:
            msg = str(e).replace('\n', ' ')
            msg = ' '.join(msg.split())
            log.critical(msg, exc_info=False)
            if output_to_console:
                print('')
                print('-' * 79)
                print(' Malformed configuration file (check messages above). Common reasons:')
                print('-' * 79)
                print('')
                print(' o Indentation error')
                print(' o Missing : from end of the line')
                print(' o Non ASCII characters (use UTF8)')
                print(' o If text contains any of :[]{}% characters it must be single-quoted '
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
                        print(' Check configuration near line %s, column %s' % (
                            e.context_mark.line, e.context_mark.column))
                        lines += 1
                    if e.problem_mark is not None:
                        print(' Check configuration near line %s, column %s' % (
                            e.problem_mark.line, e.problem_mark.column))
                        lines += 1
                    if lines:
                        print('')
                    if lines == 1:
                        print(' Fault is almost always in this or previous line\n')
                    if lines == 2:
                        print(' Fault is almost always in one of these lines or previous ones\n')

            # When --debug escalate to full stacktrace
            if self.options.debug or not output_to_console:
                raise
            raise ValueError('Config file is not valid YAML')

        # config loaded successfully
        log.debug('config_name: %s' % self.config_name)
        log.debug('config_base: %s' % self.config_base)
        # Install the newly loaded config
        self.update_config(config)

    def update_config(self, config):
        """
        Provide a new config for the manager to use.

        :raises: `ValueError` and rolls back to previous config if the provided config is not valid.
        """
        new_user_config = config
        old_config = self.config
        try:
            self.config = self.validate_config(config)
        except ValueError as e:
            for error in getattr(e, 'errors', []):
                log.critical('[%s] %s', error.json_pointer, error.message)
            log.debug('invalid config, rolling back')
            self.config = old_config
            raise
        log.debug('New config data loaded.')
        self.user_config = copy.deepcopy(new_user_config)
        fire_event('manager.config_updated', self)

    def backup_config(self):
        backup_path = os.path.join(self.config_base,
                                   '%s-%s.bak' % (self.config_name, datetime.now().strftime('%y%m%d%H%M%S')))

        log.debug('backing up old config to %s before new save' % backup_path)
        try:
            shutil.copy(self.config_path, backup_path)
        except (OSError, IOError) as e:
            log.warning('Config backup creation failed: %s', str(e))
            raise
        return backup_path

    def save_config(self):
        """Dumps current config to yaml config file"""
        # TODO: Only keep x number of backups..

        # Back up the user's current config before overwriting
        try:
            self.backup_config()
        except (OSError, IOError):
            return
        with open(self.config_path, 'w') as config_file:
            config_file.write(yaml.dump(self.user_config, default_flow_style=False))

    def config_changed(self):
        """Makes sure that all tasks will have the config_modified flag come out true on the next run.
        Useful when changing the db and all tasks need to be completely reprocessed."""
        from flexget.task import config_changed
        config_changed()
        fire_event('manager.config_updated', self)

    def validate_config(self, config=None):
        """
        Check all root level keywords are valid. Config may be modified by before_config_validate hooks. Modified
        config will be returned.

        :param config: Config to check. If not provided, current manager config will be checked.
        :raises: `ValueError` when config fails validation. There will be an `errors` attribute with the schema errors.
        :returns: Final validated config.
        """
        if not config:
            config = self.config
        config = fire_event('manager.before_config_validate', config, self)
        errors = config_schema.process_config(config)
        if errors:
            err = ValueError('Did not pass schema validation.')
            err.errors = errors
            raise err
        else:
            return config

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
            # in case running on windows, needs double \\
            filename = self.db_filename.replace('\\', '\\\\')
            self.database_uri = 'sqlite:///%s' % filename

        if self.db_filename and not os.path.exists(self.db_filename):
            log.verbose('Creating new database %s - DO NOT INTERUPT ...' % self.db_filename)

        # fire up the engine
        log.debug('Connecting to: %s' % self.database_uri)
        try:
            self.engine = sqlalchemy.create_engine(self.database_uri,
                                                   echo=self.options.debug_sql,
                                                   connect_args={'check_same_thread': False, 'timeout': 10})
        except ImportError as e:
            print('FATAL: Unable to use SQLite. Are you running Python 2.7, 3.3 or newer ?\n'
                  'Python should normally have SQLite support built in.\n'
                  'If you\'re running correct version of Python then it is not equipped with SQLite.\n'
                  'You can try installing `pysqlite`. If you have compiled python yourself, '
                  'recompile it with SQLite support.\n'
                  'Error: %s' % e, file=sys.stderr)
            sys.exit(1)
        Session.configure(bind=self.engine)
        # create all tables, doesn't do anything to existing tables
        try:
            Base.metadata.create_all(bind=self.engine)
        except OperationalError as e:
            if os.path.exists(self.db_filename):
                print('%s - make sure you have write permissions to file %s' %
                      (e.message, self.db_filename), file=sys.stderr)
            else:
                print('%s - make sure you have write permissions to directory %s' %
                      (e.message, self.config_base), file=sys.stderr)
            raise

    def _read_lock(self):
        """
        Read the values from the lock file. Returns None if there is no current lock file.
        """
        if self.lockfile and os.path.exists(self.lockfile):
            result = {}
            with io.open(self.lockfile, encoding='utf-8') as f:
                lines = [l for l in f.readlines() if l]
            for line in lines:
                try:
                    key, value = line.split(':', 1)
                except ValueError:
                    log.debug('Invalid line in lock file: %s' % line)
                    continue
                result[key.strip().lower()] = value.strip()
            for key in result:
                if result[key].isdigit():
                    result[key] = native_int(result[key])
            result.setdefault('pid', None)
            if not result['pid']:
                log.error('Invalid lock file. Make sure FlexGet is not running, then delete it.')
            elif not pid_exists(result['pid']):
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
        :param bool event: If True, the 'manager.lock_acquired' event will be fired after a lock is obtained
        """
        acquired = False
        try:
            # Don't do anything if we already have a lock. This means only the outermost call will release the lock file
            if not self._has_lock:
                # Exit if there is an existing lock.
                if self.check_lock():
                    with io.open(self.lockfile, encoding='utf-8') as f:
                        pid = f.read()
                    print('Another process (%s) is running, will exit.' % pid.split('\n')[0], file=sys.stderr)
                    print('If you\'re sure there is no other instance running, delete %s' % self.lockfile,
                          file=sys.stderr)
                    sys.exit(1)

                self._has_lock = True
                self.write_lock()
                acquired = True
                if event:
                    fire_event('manager.lock_acquired', self)
            yield
        finally:
            if acquired:
                self.release_lock()
                self._has_lock = False

    def write_lock(self, ipc_info=None):
        assert self._has_lock
        with io.open(self.lockfile, 'w', encoding='utf-8') as f:
            f.write('PID: %s\n' % os.getpid())
            if ipc_info:
                for key in sorted(ipc_info):
                    f.write('%s: %s\n' % (key, ipc_info[key]))

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
        si = open(os.devnull, 'r')
        so = open(os.devnull, 'ab+')
        se = open(os.devnull, 'ab+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # If we have a lock, update the lock file with our new pid
        if self._has_lock:
            self.write_lock()

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
            with Session() as session:
                fire_event('manager.db_cleanup', self, session)
            # Try to VACUUM after cleanup
            fire_event('manager.db_vacuum', self)
            # Just in case some plugin was overzealous in its cleaning, mark the config changed
            self.config_changed()
            self.persist['last_cleanup'] = datetime.now()
        else:
            log.debug('Not running db cleanup, last run %s' % self.persist.get('last_cleanup'))

    def shutdown(self, finish_queue=True):
        """
        Request manager shutdown.

        :param bool finish_queue: Should scheduler finish the task queue
        """
        if not self.initialized:
            raise RuntimeError('Cannot shutdown manager that was never initialized.')
        fire_event('manager.shutdown_requested', self)
        self.task_queue.shutdown(finish_queue)

    def _shutdown(self):
        """Runs when the manager is done processing everything."""
        if self.ipc_server:
            self.ipc_server.shutdown()
        fire_event('manager.shutdown', self)
        if not self.unit_test:  # don't scroll "nosetests" summary results when logging is enabled
            log.debug('Shutting down')
        self.engine.dispose()
        # remove temporary database used in test mode
        if self.options.test:
            if 'test' not in self.db_filename:
                raise Exception('trying to delete non test database?')
            if self._has_lock:
                os.remove(self.db_filename)
                log.info('Removed test database')
        global manager
        manager = None

    def crash_report(self):
        """
        This should be called when handling an unexpected exception. Will create a new log file containing the last 50
        debug messages as well as the crash traceback.
        """
        if not self.unit_test:
            filename = os.path.join(self.config_base, datetime.now().strftime('crash_report.%Y.%m.%d.%H%M%S%f.log'))
            with codecs.open(filename, 'w', encoding='utf-8') as outfile:
                outfile.writelines(logger.debug_buffer)
                traceback.print_exc(file=outfile)
            log.critical('An unexpected crash has occurred. Writing crash report to %s. '
                         'Please verify you are running the latest version of flexget by using "flexget -V" '
                         'from CLI or by using version_checker plugin'
                         ' at http://flexget.com/wiki/Plugins/version_checker. You are currently using'
                         ' version %s', filename, get_current_flexget_version())
        log.debug('Traceback:', exc_info=True)
        return traceback.format_exc()
