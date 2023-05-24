import argparse
import atexit
import codecs
import collections
import copy
import errno
import fnmatch
import hashlib
import os
import shutil
import signal
import sys
import threading
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import (
    TYPE_CHECKING,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

import sqlalchemy
import yaml
from loguru import logger
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# These need to be declared before we start importing from other flexget modules, since they might import them
from flexget.config_schema import ConfigError
from flexget.utils.sqlalchemy_utils import ContextSession
from flexget.utils.tools import get_current_flexget_version, io_encoding, pid_exists

Base = declarative_base()
Session: Type[ContextSession] = sessionmaker(class_=ContextSession)

import flexget.log  # noqa
from flexget import config_schema, db_schema, plugin  # noqa
from flexget.event import fire_event  # noqa
from flexget.ipc import IPCClient, IPCServer  # noqa
from flexget.options import CoreArgumentParser, ParserError, get_parser, manager_parser  # noqa
from flexget.task import Task  # noqa
from flexget.task_queue import TaskQueue  # noqa
from flexget.terminal import console, get_console_output  # noqa

if TYPE_CHECKING:
    from flexget.tray_icon import TrayIcon
    from flexget.utils.simple_persistence import SimplePersistence

logger = logger.bind(name='manager')

manager: Optional['Manager'] = None
DB_CLEANUP_INTERVAL = timedelta(days=7)


class Manager:
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

      After manager has been initialized. This is when application becomes ready to use,
      however no database lock is present, so the database must not be modified on this event.

    * manager.lock_acquired

      The manager does not always require a lock on startup, if one is requested,
      this event will run when it has been acquired successfully

    * manager.upgrade

      If any plugins have declared a newer schema version than exists in the database,
      this event will be fired to allow plugins to upgrade their tables

    * manager.shutdown_requested

      When shutdown has been requested. Any plugins which might add to
      execution queue should stop when this is fired.

    * manager.shutdown

      When the manager is exiting

    * manager.execute.completed

      If execution in current process was completed

    * manager.daemon.started
    * manager.daemon.completed
    * manager.db_cleanup
    """

    unit_test = False
    options: argparse.Namespace

    def __init__(self, args: List[str]) -> None:
        """
        :param args: CLI args
        """
        global manager
        if not self.unit_test:
            assert not manager, 'Only one instance of Manager should be created at a time!'
        elif manager:
            logger.info('last manager was not torn down correctly')

        self.args = args
        self.autoreload_config = False
        self.config_file_hash: Optional[str] = None
        self.config_base: str = ''
        self.config_name: str = ''
        self.config_path: str = ''
        self.log_filename: str = ''
        self.db_filename: str = ''
        self.engine: Optional[Engine] = None
        self.lockfile: str = ''
        self.database_uri: str = ''
        self.db_upgraded = False
        self._has_lock = False
        self.is_daemon = False
        self.ipc_server: IPCServer
        self.task_queue: TaskQueue
        self.persist: 'SimplePersistence'
        self.initialized = False

        self.config: Dict = {}

        self.options = self.parse_initial_options(args)
        self._init_config(create=False)
        # When we are in test mode, we use a different lock file and db
        if self.options.test:
            self.lockfile = os.path.join(self.config_base, f'.test-{self.config_name}-lock')
        self._init_logging()

        manager = self

        logger.debug('sys.defaultencoding: {}', sys.getdefaultencoding())
        logger.debug('sys.getfilesystemencoding: {}', sys.getfilesystemencoding())
        logger.debug('flexget detected io encoding: {}', io_encoding)
        logger.debug('os.path.supports_unicode_filenames: {}', os.path.supports_unicode_filenames)
        if (
            codecs.lookup(sys.getfilesystemencoding()).name == 'ascii'
            and not os.path.supports_unicode_filenames
        ):
            logger.warning(
                'Your locale declares ascii as the filesystem encoding. Any plugins reading filenames from '
                'disk will not work properly for filenames containing non-ascii characters. Make sure your '
                'locale env variables are set up correctly for the environment which is launching FlexGet.'
            )

    def _add_tray_icon_items(self, tray_icon: 'TrayIcon'):
        tray_icon.add_menu_item(text='Shutdown', action=self.shutdown, index=2)
        tray_icon.add_menu_item(text='Reload Config', action=self.load_config, index=3)
        tray_icon.add_menu_separator(index=4)

    @staticmethod
    def parse_initial_options(args: List[str]) -> argparse.Namespace:
        """Parse what we can from cli args before plugins are loaded."""
        try:
            options = CoreArgumentParser().parse_known_args(args, do_help=False)[0]
        except ParserError as exc:
            try:
                # If a non-built-in command was used, we need to parse with a parser that
                # doesn't define the subparsers
                options = manager_parser.parse_known_args(args, do_help=False)[0]
            except ParserError:
                manager_parser.print_help()
                print(f'\nError: {exc.message}')
                sys.exit(1)
        return options

    def _init_logging(self) -> None:
        """Initialize logging variables"""
        log_file = os.path.expanduser(self.options.logfile)
        # If an absolute path is not specified, use the config directory.
        if not os.path.isabs(log_file):
            log_file = os.path.join(self.config_base, log_file)
        self.log_filename = log_file

    def initialize(self) -> None:
        """
        Load plugins, database, and config. Also initializes (but does not start) the task queue and ipc server.
        This should only be called after obtaining a lock.
        """
        if self.initialized:
            raise RuntimeError('Cannot call initialize on an already initialized manager.')

        plugin.load_plugins(
            extra_plugins=[os.path.join(self.config_base, 'plugins')],
            extra_components=[os.path.join(self.config_base, 'components')],
        )

        # Reparse CLI options now that plugins are loaded
        self.options = get_parser().parse_args(self.args)

        self.task_queue = TaskQueue()
        self.ipc_server = IPCServer(self, self.options.ipc_port)

        self.setup_yaml()
        self.init_sqlalchemy()
        fire_event('manager.initialize', self)
        try:
            self.load_config()
        except ValueError as e:
            logger.critical('Failed to load config file: {}', e.args[0])
            raise

        # cannot be imported at module level because of circular references
        from flexget.utils.simple_persistence import SimplePersistence

        self.persist = SimplePersistence('manager')

        if db_schema.upgrade_required():
            logger.info('Database upgrade is required. Attempting now.')
            fire_event('manager.upgrade', self)
            if manager.db_upgraded:
                fire_event('manager.db_upgraded', self)
        fire_event('manager.startup', self)
        self.initialized = True

    @property
    def tasks(self) -> List[str]:
        """A list of tasks in the config"""
        if not self.config:
            return []
        return list(self.config.get('tasks', {}).keys())

    @property
    def has_lock(self) -> bool:
        return self._has_lock

    def execute(
        self,
        options: Union[dict, argparse.Namespace] = None,
        priority: int = 1,
        suppress_warnings: Sequence[str] = None,
    ) -> List[Tuple[str, str, threading.Event]]:
        """
        Run all (can be limited with options) tasks from the config.

        :param options: Either an :class:`argparse.Namespace` instance, or a dict, containing options for execution
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
            logger.info('Config change detected. Reloading.')
            try:
                self.load_config(output_to_console=False, config_file_hash=config_hash)
                logger.info('Config successfully reloaded!')
            except Exception as e:
                logger.error('Reloading config failed: {}', e)
        # Handle --tasks
        if options.tasks:
            # Consider '*' the same as not specifying any tasks.
            # (So manual plugin doesn't consider them explicitly enabled.)
            if options.tasks == ['*']:
                options.tasks = None
            else:
                task_names = []
                for task in options.tasks:
                    try:
                        task_names.extend(
                            m for m in self.matching_tasks(task) if m not in task_names
                        )
                    except ValueError as e:
                        logger.error(e)
                        continue
                options.tasks = task_names
        # TODO: 1.2 This is a hack to make task priorities work still, not sure if it's the best one
        task_names = sorted(
            task_names, key=lambda t: self.config['tasks'][t].get('priority', 65535)
        )

        finished_events = []
        for task_name in task_names:
            task = Task(
                self,
                task_name,
                options=options,
                output=get_console_output(),
                session_id=flexget.log.get_log_session_id(),
                priority=priority,
                suppress_warnings=suppress_warnings,
            )
            self.task_queue.put(task)
            finished_events.append((task.id, task.name, task.finished_event))
        return finished_events

    def start(self) -> None:
        """
        Starting point when executing from commandline, dispatch execution to correct destination.

        If there is a FlexGet process with an ipc server already running, the command will be sent there for execution
        and results will be streamed back.
        If not, this will attempt to obtain a lock, initialize the manager, and run the command here.
        """
        # If another process is started, send the execution to the running process
        ipc_info = self.check_ipc_info()
        # If we are connecting to a running daemon, we don't want to log to the log file,
        # the daemon is already handling that.
        if ipc_info:
            console(
                'There is a FlexGet process already running for this config, sending execution there.'
            )
            logger.debug('Sending command to running FlexGet process: {}', self.args)
            try:
                client = IPCClient(ipc_info['port'], ipc_info['password'])
            except ValueError as e:
                logger.error(e)
            else:
                try:
                    client.handle_cli(self.args)
                except KeyboardInterrupt:
                    logger.error(
                        'Disconnecting from daemon due to ctrl-c. Executions will still continue in the '
                        'background.'
                    )
                except EOFError:
                    logger.error('Connection from daemon was severed.')
            return
        if self.options.test:
            logger.info('Test mode, creating a copy from database ...')
            db_test_filename = os.path.join(self.config_base, f'test-{self.config_name}.sqlite')
            if os.path.exists(self.db_filename):
                shutil.copy(self.db_filename, db_test_filename)
                logger.info('Test database created')
            self.db_filename = db_test_filename
        # No running process, we start our own to handle command
        with self.acquire_lock():
            self.initialize()
            self.handle_cli()
            self._shutdown()

    def handle_cli(self, options: argparse.Namespace = None) -> None:
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

    def execute_command(self, options: argparse.Namespace) -> None:
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
                logger.error(
                    'Task queue has died unexpectedly. Restarting it. Please open an issue on Github and include'
                    ' any previous error logs.'
                )
                self.task_queue = TaskQueue()
                self.task_queue.start()
            if len(self.task_queue):
                logger.verbose('There is a task already running, execution queued.')
            finished_events = self.execute(options)
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

    def daemon_command(self, options: argparse.Namespace) -> None:
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
                logger.error('Daemon already running for this config.')
                return
            elif self.task_queue.is_alive():
                logger.error(
                    'Non-daemon execution of FlexGet is running. Cannot start daemon until it is finished.'
                )
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
                logger.debug('Error registering sigterm handler: {}', e)
            self.is_daemon = True

            def run_daemon(tray_icon: 'TrayIcon' = None):
                fire_event('manager.daemon.started', self)
                self.task_queue.start()
                self.ipc_server.start()
                self.task_queue.wait()
                fire_event('manager.daemon.completed', self)
                if tray_icon:
                    tray_icon.stop()

            if options.tray_icon:
                from flexget.tray_icon import tray_icon

                self._add_tray_icon_items(tray_icon)

                # Tray icon must be run in the main thread.
                m = threading.Thread(target=run_daemon, args=(tray_icon,))
                m.start()
                tray_icon.run()
                m.join()
            else:
                run_daemon()

        elif options.action in ['stop', 'reload-config', 'status']:
            if not self.is_daemon:
                console('There does not appear to be a daemon running.')
                return
            if options.action == 'status':
                logger.debug('`daemon status` called. Daemon running. (PID: {})', os.getpid())
                console(f'Daemon running. (PID: {os.getpid()})')
            elif options.action == 'stop':
                tasks = (
                    'all queued tasks (if any) have'
                    if options.wait
                    else 'currently running task (if any) has'
                )
                logger.info(
                    'Daemon shutdown requested. Shutdown will commence when {} finished executing.',
                    tasks,
                )
                self.shutdown(options.wait)
            elif options.action == 'reload-config':
                logger.info('Reloading config from disk.')
                try:
                    self.load_config()
                except ValueError as e:
                    logger.error('Error loading config: {}', e.args[0])
                else:
                    logger.info('Config successfully reloaded from disk.')

    def _handle_sigterm(self, signum, frame) -> None:
        logger.info('Got SIGTERM. Shutting down.')
        self.shutdown(finish_queue=False)

    def setup_yaml(self) -> None:
        """Customize the yaml loader/dumper behavior"""

        # Represent OrderedDict as a regular dict (but don't sort it alphabetically)
        # This lets us order a dict in a yaml file for easier human consumption
        def represent_dict_order(self, data):
            return self.represent_mapping('tag:yaml.org,2002:map', data.items())

        yaml.add_representer(collections.OrderedDict, represent_dict_order)

        # Set up the dumper to increase the indent for lists
        def increase_indent_wrapper(func):
            def increase_indent(self, flow=False, indentless=False):
                func(self, flow, False)

            return increase_indent

        yaml.Dumper.increase_indent = increase_indent_wrapper(yaml.Dumper.increase_indent)
        yaml.SafeDumper.increase_indent = increase_indent_wrapper(yaml.SafeDumper.increase_indent)

    def _init_config(self, create: bool = False) -> None:
        """
        Find and load the configuration file.

        :param bool create: If a config file is not found, and create is True, one will be created in the home folder
        :raises: `OSError` when no config file could be found, and `create` is False.
        """
        home_path = os.path.join(os.path.expanduser('~'), '.flexget')
        options_config = os.path.expanduser(self.options.config)

        possible = []
        if os.path.isabs(options_config):
            # explicit path given, don't try anything
            config = options_config
            possible = [config]
        else:
            logger.debug('Figuring out config load paths')
            try:
                possible.append(os.getcwd())
            except OSError:
                logger.debug('current directory invalid, not searching for config there')
            # for virtualenv / dev sandbox
            if hasattr(sys, 'real_prefix'):
                logger.debug('Adding virtualenv path')
                possible.append(sys.prefix)
            # normal lookup locations
            possible.append(home_path)
            if sys.platform.startswith('win'):
                # On windows look in ~/flexget as well, as explorer does not let you create a folder starting with a dot
                home_path = os.path.join(os.path.expanduser('~'), 'flexget')
                possible.append(home_path)
            else:
                # The freedesktop.org standard config location
                xdg_config = os.environ.get(
                    'XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config')
                )
                possible.append(os.path.join(xdg_config, 'flexget'))

            for path in possible:
                config = os.path.join(path, options_config)
                if os.path.exists(config):
                    logger.debug('Found config: {}', config)
                    break
            else:
                config = None

        if create and not (config and os.path.exists(config)):
            config = os.path.join(home_path, options_config)
            logger.info('Config file {} not found. Creating new config {}', options_config, config)
            with open(config, 'w') as newconfig:
                # Write empty tasks to the config
                newconfig.write(yaml.dump({'tasks': {}}))
        elif not config:
            logger.critical('Failed to find configuration file {}', options_config)
            logger.info('Tried to read from: {}', ', '.join(possible))
            raise OSError('No configuration file found.')
        if not os.path.isfile(config):
            raise OSError(f'Config `{config}` does not appear to be a file.')

        logger.debug('Config file {} selected', config)
        self.config_path = config
        self.config_name = os.path.splitext(os.path.basename(config))[0]
        self.config_base = os.path.normpath(os.path.dirname(config))
        self.lockfile = os.path.join(self.config_base, f'.{self.config_name}-lock')
        self.db_filename = os.path.join(self.config_base, f'db-{self.config_name}.sqlite')

    def hash_config(self) -> Optional[str]:
        if not self.config_path:
            return None
        sha1_hash = hashlib.sha1()
        with open(self.config_path, 'rb') as f:
            while True:
                data = f.read(65536)
                if not data:
                    break
                sha1_hash.update(data)
        return sha1_hash.hexdigest()

    def load_config(self, output_to_console: bool = True, config_file_hash: str = None) -> None:
        """
        Loads the config file from disk, validates and activates it.

        :raises: `ValueError` if there is a problem loading the config file
        """
        fire_event('manager.before_config_load', self)
        with open(self.config_path, encoding='utf-8') as f:
            try:
                raw_config = f.read()
            except UnicodeDecodeError:
                logger.critical('Config file must be UTF-8 encoded.')
                raise ValueError('Config file is not UTF-8 encoded')
        try:
            self.config_file_hash = config_file_hash or self.hash_config()
            config = yaml.safe_load(raw_config) or {}
        except yaml.YAMLError as e:
            msg = str(e).replace('\n', ' ')
            msg = ' '.join(msg.split())
            logger.critical(msg)
            if output_to_console:
                print('')
                print('-' * 79)
                print(' Malformed configuration file (check messages above). Common reasons:')
                print('-' * 79)
                print('')
                print(' o Indentation error')
                print(' o Missing : from end of the line')
                print(' o Non ASCII characters (use UTF8)')
                print(
                    ' o If text contains any of :[]{}% characters it must be single-quoted '
                    '(eg. value{1} should be \'value{1}\')\n'
                )

                # Not very good practice but we get several kind of exceptions here, I'm not even sure all of them
                # At least: ReaderError, YmlScannerError (or something like that)
                if isinstance(e, yaml.MarkedYAMLError):
                    lines = 0
                    if e.problem is not None:
                        print(f' Reason: {e.problem}\n')
                        if e.problem == 'mapping values are not allowed here':
                            print(' ----> MOST LIKELY REASON: Missing : from end of the line!')
                            print('')
                    if e.context_mark is not None:
                        print(
                            f' Check configuration near line {e.context_mark.line}, column {e.context_mark.column}'
                        )
                        lines += 1
                    if e.problem_mark is not None:
                        print(
                            f' Check configuration near line {e.problem_mark.line}, column {e.problem_mark.column}'
                        )
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
        logger.debug('config_name: {}', self.config_name)
        logger.debug('config_base: {}', self.config_base)
        # Install the newly loaded config
        self.update_config(config)

    def update_config(self, config: dict) -> None:
        """
        Provide a new config for the manager to use.

        :raises: `ValueError` and rolls back to previous config if the provided config is not valid.
        """
        new_user_config = config
        old_config = self.config
        try:
            self.config = self.validate_config(config)
        except ConfigError as e:
            for error in getattr(e, 'errors', []):
                logger.critical('[{}] {}', error.json_pointer, error.message)
            logger.debug('invalid config, rolling back')
            self.config = old_config
            raise
        logger.debug('New config data loaded.')
        self.user_config = copy.deepcopy(new_user_config)
        fire_event('manager.config_updated', self)

    def backup_config(self) -> str:
        backup_path = os.path.join(
            self.config_base,
            f'{self.config_name}-{datetime.now().strftime("%y%m%d%H%M%S")}.bak',
        )

        logger.debug(f'backing up old config to {backup_path} before new save')
        try:
            shutil.copy(self.config_path, backup_path)
        except OSError as e:
            logger.warning(f'Config backup creation failed: {e}')
            raise
        return backup_path

    def save_config(self) -> None:
        """Dumps current config to yaml config file"""
        # TODO: Only keep x number of backups..

        # Back up the user's current config before overwriting
        try:
            self.backup_config()
        except OSError:
            return
        with open(self.config_path, 'w') as config_file:
            config_file.write(yaml.dump(self.user_config, default_flow_style=False))

    def config_changed(self) -> None:
        """Makes sure that all tasks will have the config_modified flag come out true on the next run.
        Useful when changing the db and all tasks need to be completely reprocessed."""
        from flexget.task import config_changed

        config_changed()
        fire_event('manager.config_updated', self)

    def validate_config(self, config: dict = None) -> dict:
        """
        Check all root level keywords are valid. Config may be modified by before_config_validate hooks. Modified
        config will be returned.

        :param config: Config to check. If not provided, current manager config will be checked.
        :raises: `ValueError` when config fails validation. There will be an `errors` attribute with the schema errors.
        :returns: Final validated config.
        """
        conf = config if config else self.config
        conf = fire_event('manager.before_config_validate', conf, self)
        errors = config_schema.process_config(conf)
        if errors:
            err = ConfigError('Did not pass schema validation.')
            err.errors = errors
            raise err
        else:
            return conf

    def init_sqlalchemy(self) -> None:
        """Initialize SQLAlchemy"""
        try:
            if [int(part) for part in sqlalchemy.__version__.split('.')] < [0, 7, 0]:
                print(
                    'FATAL: SQLAlchemy 0.7.0 or newer required. Please upgrade your SQLAlchemy.',
                    file=sys.stderr,
                )
                sys.exit(1)
        except ValueError:
            logger.critical('Failed to check SQLAlchemy version, you may need to upgrade it')

        # SQLAlchemy
        if not self.database_uri:
            # in case running on windows, needs double \\
            filename = self.db_filename.replace('\\', '\\\\')
            self.database_uri = f'sqlite:///{filename}'

        if self.db_filename and not os.path.exists(self.db_filename):
            logger.verbose('Creating new database {} - DO NOT INTERRUPT ...', self.db_filename)

        # fire up the engine
        logger.debug('Connecting to: {}', self.database_uri)
        try:
            self.engine = sqlalchemy.create_engine(
                self.database_uri,
                echo=self.options.debug_sql,
                connect_args={'check_same_thread': False, 'timeout': 10},
            )
        except ImportError as e:
            print(
                'FATAL: Unable to use SQLite. Are you running Python 2.7, 3.3 or newer ?\n'
                'Python should normally have SQLite support built in.\n'
                'If you\'re running correct version of Python then it is not equipped with SQLite.\n'
                'You can try installing `pysqlite`. If you have compiled python yourself, '
                'recompile it with SQLite support.\n'
                f'Error: {e}',
                file=sys.stderr,
            )
            sys.exit(1)
        Session.configure(bind=self.engine)
        # create all tables, doesn't do anything to existing tables
        try:
            Base.metadata.create_all(bind=self.engine)
        except OperationalError as e:
            if os.path.exists(self.db_filename):
                print(
                    f'{e.message} - make sure you have write permissions to file {self.db_filename}',
                    file=sys.stderr,
                )
            else:
                print(
                    f'{e.message} - make sure you have write permissions to directory {self.config_base}',
                    file=sys.stderr,
                )
            raise

    def _read_lock(self) -> Optional[dict]:
        """
        Read the values from the lock file. Returns None if there is no current lock file.
        """
        if self.lockfile and os.path.exists(self.lockfile):
            result: Dict[str, Union[str, int]] = {}
            with open(self.lockfile, encoding='utf-8') as f:
                lines = [line for line in f.readlines() if line]
            for line in lines:
                try:
                    key, value = line.split(':', 1)
                except ValueError:
                    logger.debug('Invalid line in lock file: {}', line)
                    continue
                result[key.strip().lower()] = value.strip()
            for key in result:
                if result[key].isdigit():
                    result[key] = int(result[key])
            result.setdefault('pid', None)
            if not result['pid']:
                logger.error(
                    'Invalid lock file. Make sure FlexGet is not running, then delete it.'
                )
            elif not pid_exists(result['pid']):
                return None
            return result
        return None

    def check_lock(self) -> bool:
        """Returns True if there is a lock on the database."""
        lock_info = self._read_lock()
        if not lock_info:
            return False
        # Don't count it if we hold the lock
        if os.getpid() == lock_info['pid']:
            return False
        return True

    def check_ipc_info(self) -> Optional[dict]:
        """If a daemon has a lock on the database, return info to connect to IPC."""
        lock_info = self._read_lock()
        if lock_info and 'port' in lock_info:
            return lock_info
        return None

    @contextmanager
    def acquire_lock(self, event: bool = True) -> Iterator:
        """
        :param bool event: If True, the 'manager.lock_acquired' event will be fired after a lock is obtained
        """
        acquired = False
        try:
            # Don't do anything if we already have a lock. This means only the outermost call will release the lock file
            if not self._has_lock:
                # Exit if there is an existing lock.
                if self.check_lock():
                    with open(self.lockfile, encoding='utf-8') as f:
                        pid = f.read()
                    print(
                        'Another process (%s) is running, will exit.' % pid.split('\n')[0],
                        file=sys.stderr,
                    )
                    print(
                        "If you're sure there is no other instance running, delete %s"
                        % self.lockfile,
                        file=sys.stderr,
                    )
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

    def write_lock(self, ipc_info: dict = None) -> None:
        assert self._has_lock
        with open(self.lockfile, 'w', encoding='utf-8') as f:
            f.write(f'PID: {os.getpid()}\n')
            if ipc_info:
                for key in sorted(ipc_info):
                    f.write(f'{key}: {ipc_info[key]}\n')

    def release_lock(self) -> None:
        try:
            os.remove(self.lockfile)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
            logger.debug(f'Lockfile {self.lockfile} not found')
        else:
            logger.debug(f'Removed {self.lockfile}')

    def daemonize(self) -> None:
        """Daemonizes the current process. Returns the new pid"""
        if sys.platform.startswith('win'):
            logger.error('Cannot daemonize on windows')
            return
        if threading.active_count() != 1:
            logger.critical(
                'There are {!r} active threads. Daemonizing now may cause strange failures.',
                threading.enumerate(),
            )

        logger.info('Daemonizing...')

        try:
            pid = os.fork()
            if pid > 0:
                # Don't run the exit handlers on the parent
                atexit._exithandlers = []
                # exit first parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(f'fork #1 failed: {e.errno} ({e.strerror})\n')
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
            sys.stderr.write(f'fork #2 failed: {e.errno} ({e.strerror})\n')
            sys.exit(1)

        logger.info(f'Daemonize complete. New PID: {os.getpid()}')
        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = open(os.devnull)
        so = open(os.devnull, 'ab+')
        se = open(os.devnull, 'ab+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # If we have a lock, update the lock file with our new pid
        if self._has_lock:
            self.write_lock()

    def db_cleanup(self, force: bool = False) -> None:
        """
        Perform database cleanup if cleanup interval has been met.

        Fires events:

        * manager.db_cleanup

          If interval was met. Gives session to do the cleanup as a parameter.

        :param bool force: Run the cleanup no matter whether the interval has been met.
        """
        expired = (
            self.persist.get('last_cleanup', datetime(1900, 1, 1))
            < datetime.now() - DB_CLEANUP_INTERVAL
        )
        if force or expired:
            logger.info('Running database cleanup.')
            with Session() as session:
                fire_event('manager.db_cleanup', self, session)
            # Try to VACUUM after cleanup
            fire_event('manager.db_vacuum', self)
            # Just in case some plugin was overzealous in its cleaning, mark the config changed
            self.config_changed()
            self.persist['last_cleanup'] = datetime.now()
        else:
            logger.debug('Not running db cleanup, last run {}', self.persist.get('last_cleanup'))

    def shutdown(self, finish_queue: bool = True) -> None:
        """
        Request manager shutdown.

        :param bool finish_queue: Should scheduler finish the task queue
        """
        if not self.initialized:
            raise RuntimeError('Cannot shutdown manager that was never initialized.')
        fire_event('manager.shutdown_requested', self)
        self.task_queue.shutdown(finish_queue)

    def _shutdown(self) -> None:
        """Runs when the manager is done processing everything."""
        if self.ipc_server:
            self.ipc_server.shutdown()
        fire_event('manager.shutdown', self)
        if not self.unit_test:  # don't scroll "nosetests" summary results when logging is enabled
            logger.debug('Shutting down')
        self.engine.dispose()
        # remove temporary database used in test mode
        if self.options.test:
            if 'test' not in self.db_filename:
                raise Exception('trying to delete non test database?')
            if self._has_lock:
                os.remove(self.db_filename)
                logger.info('Removed test database')
        global manager
        manager = None

    def matching_tasks(self, task: str) -> Optional[List[str]]:
        """Create list of tasks to run, preserving order"""
        task_names = [t for t in self.tasks if fnmatch.fnmatchcase(str(t).lower(), task.lower())]
        if not task_names:
            raise ValueError(f'`{task}` does not match any tasks')

        return task_names

    def crash_report(self) -> str:
        """
        This should be called when handling an unexpected exception. Will create a new log file containing the last 50
        debug messages as well as the crash traceback.
        """
        if not self.unit_test:
            log_dir = os.path.dirname(self.log_filename)
            filename = os.path.join(
                log_dir, datetime.now().strftime('crash_report.%Y.%m.%d.%H%M%S%f.log')
            )
            with codecs.open(filename, 'w', encoding='utf-8') as outfile:
                outfile.writelines(flexget.log.debug_buffer)
                traceback.print_exc(file=outfile)
            logger.critical(
                'An unexpected crash has occurred. Writing crash report to {}. '
                'Please verify you are running the latest version of flexget by using "flexget -V" '
                'from CLI or by using version_checker plugin'
                ' at https://flexget.com/Plugins/version_checker. '
                'You are currently using version {}',
                filename,
                get_current_flexget_version(),
            )
        logger.opt(exception=True).debug('Traceback:')
        return traceback.format_exc()
