import copy
import random
import string
import sys
from argparse import _UNRECOGNIZED_ARGS_ATTR, PARSER, REMAINDER, SUPPRESS, Action, ArgumentError
from argparse import ArgumentParser as ArgParser
from argparse import Namespace, _SubParsersAction, _VersionAction
from typing import Any, Callable, List, Optional, TextIO, IO

import flexget
from flexget.entry import Entry
from flexget.event import fire_event
from flexget.utils.tools import get_current_flexget_version, get_latest_flexget_version_number

_UNSET = object()

core_parser: Optional['CoreArgumentParser'] = None


def unicode_argv() -> List[str]:
    """Like sys.argv, but decodes all arguments."""
    args = []
    for arg in sys.argv:
        if isinstance(arg, bytes):
            arg = arg.decode(sys.getfilesystemencoding())
        args.append(arg)
    return args


def get_parser(command: str = None) -> 'ArgumentParser':
    global core_parser
    if not core_parser:
        core_parser = CoreArgumentParser()
        # Add all plugin options to the parser
        fire_event('options.register')
    if command:
        return core_parser.get_subparser(command)
    return core_parser


def register_command(
    command: str, callback: Callable[['flexget.manager.Manager', Namespace], Any], **kwargs
) -> 'ArgumentParser':
    """
    Register a callback function to be executed when flexget is launched with the given `command`.

    :param command: The command being defined.
    :param callback: Callback function executed when this command is invoked from the CLI. Should take manager instance
        and parsed argparse namespace as parameters.
    :param kwargs: Other keyword arguments will be passed to the :class:`arparse.ArgumentParser` constructor
    :returns: An :class:`argparse.ArgumentParser` instance ready to be configured with the options for this command.
    """
    return get_parser().add_subparser(
        command, parent_defaults={'cli_command_callback': callback}, **kwargs
    )


def required_length(nmin: int, nmax: int):
    """Generates a custom Action to validate an arbitrary range of arguments."""

    class RequiredLength(Action):
        def __call__(self, parser: ArgParser, args, values, option_string=None):
            if not nmin <= len(values) <= nmax:
                raise ArgumentError(self, 'requires between %s and %s arguments' % (nmin, nmax))
            setattr(args, self.dest, values)

    return RequiredLength


class VersionAction(_VersionAction):
    """Action to print the current version. Also checks latest release revision."""

    def __call__(self, parser: ArgParser, namespace: Namespace, values, option_string=None):
        from flexget.terminal import console

        current = get_current_flexget_version()
        latest = get_latest_flexget_version_number()

        # Print the version number
        console('%s' % get_current_flexget_version())
        # Check for latest version from server
        if latest:
            if current == latest:
                console('You are on the latest release.')
            else:
                console('Latest release: %s' % latest)
        else:
            console(
                'Error getting latest version number from https://pypi.python.org/pypi/FlexGet'
            )
        parser.exit()


class HelpAction(Action):
    """Override the default help command so that we can conditionally disable it to prevent program exit."""

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(parser, 'do_help', True):
            parser.print_help()
            parser.exit()


class DebugAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True)
        namespace.loglevel = 'DEBUG'


class DebugTraceAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True)
        namespace.debug = True
        namespace.log_level = 'trace'


class CronAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True)
        # Only set loglevel if it has not already explicitly been set
        if not hasattr(namespace, 'loglevel'):
            namespace.loglevel = 'INFO'


# This makes the old --inject form forwards compatible
class InjectAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        kwargs = {'title': values.pop(0)}
        if values:
            kwargs['url'] = values.pop(0)
        else:
            kwargs['url'] = 'http://localhost/inject/%s' % ''.join(
                random.sample(string.ascii_letters + string.digits, 30)
            )
        if 'force' in [v.lower() for v in values]:
            kwargs['immortal'] = True
        entry = Entry(**kwargs)
        if 'accept' in [v.lower() for v in values]:
            entry.accept(reason='accepted by --inject')
        existing = getattr(namespace, self.dest, None) or []
        setattr(namespace, self.dest, existing + [entry])


class ParseExtrasAction(Action):
    """This action will take extra arguments, and parser them with a different parser."""

    def __init__(self, option_strings, parser, help=None, metavar=None, dest=None, required=False):
        if metavar is None:
            metavar = '<%s arguments>' % parser.prog
        if help is None:
            help = 'arguments for the `%s` command are allowed here' % parser.prog
        self._parser = parser
        super().__init__(
            option_strings=option_strings,
            dest=SUPPRESS,
            help=help,
            metavar=metavar,
            nargs=REMAINDER,
            required=required,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        namespace, extras = self._parser.parse_known_args(values, namespace)
        if extras:
            parser.error('unrecognized arguments: %s' % ' '.join(extras))


class ScopedNamespace(Namespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__parent__ = None

    def __getattr__(self, key):
        if '.' in key:
            scope, key = key.split('.', 1)
            return getattr(getattr(self, scope), key)

        if self.__parent__:
            return getattr(self.__parent__, key)
        raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, key))

    def __setattr__(self, key: str, value):
        if '.' in key:
            scope, key = key.split('.', 1)
            if not hasattr(self, scope):
                setattr(self, scope, type(self)())
            sub_ns = getattr(self, scope, None)
            return object.__setattr__(sub_ns, key, value)
        # Let child namespaces keep track of us
        if key != '__parent__' and isinstance(value, ScopedNamespace):
            value.__parent__ = self
        return object.__setattr__(self, key, value)

    def __iter__(self):
        return (i for i in self.__dict__.items() if i[0] != '__parent__')

    def __copy__(self):
        new = self.__class__()
        new.__dict__.update(self.__dict__)
        # Make copies of any nested namespaces
        for key, value in self:
            if isinstance(value, ScopedNamespace):
                setattr(new, key, copy.copy(value))
        return new


class NestedSubparserAction(_SubParsersAction):
    def __init__(self, *args, **kwargs):
        self.nested_namespaces = kwargs.pop('nested_namespaces', False)
        self.parent_defaults = {}
        # Python < 3.7 doesn't support the 'required' argument for subparsers
        required = kwargs.pop('required', True)
        super().__init__(*args, **kwargs)
        self.required = required

    def add_parser(self, name: str, parent_defaults: dict = None, **kwargs):
        if parent_defaults:
            self.parent_defaults[name] = parent_defaults
        return super().add_parser(name, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        parser_name = values[0]
        if parser_name in self.parent_defaults:
            for dest in self.parent_defaults[parser_name]:
                if not hasattr(namespace, dest):
                    setattr(namespace, dest, self.parent_defaults[parser_name][dest])
        if self.nested_namespaces:
            subnamespace = ScopedNamespace()
            super().__call__(parser, subnamespace, values, option_string)
            # If dest is set, it should be set on the parent namespace, not subnamespace
            if self.dest is not SUPPRESS:
                setattr(namespace, self.dest, parser_name)
                delattr(subnamespace, self.dest)
            setattr(namespace, parser_name, subnamespace)
            # Propagate unrecognized arguments back to parent namespace
            vars(namespace).setdefault(_UNRECOGNIZED_ARGS_ATTR, [])
            getattr(namespace, _UNRECOGNIZED_ARGS_ATTR).extend(
                getattr(subnamespace, _UNRECOGNIZED_ARGS_ATTR)
            )
        else:
            super().__call__(parser, namespace, values, option_string)


class ParserError(Exception):
    def __init__(self, message, parser):
        self.message = message
        self.parser = parser

    def __unicode__(self):
        return self.message

    def __repr__(self):
        return 'ParserError(%s, %s)' % (self.message, self.parser)


class ArgumentParser(ArgParser):
    """
    Mimics the default :class:`argparse.ArgumentParser` class, with a few distinctions, mostly to ease subparser usage:

    - If `add_subparsers` is called with the `nested_namespaces` kwarg, all subcommand options will be stored in a
      nested namespace based on the command name for the subparser
    - Adds the `add_subparser` method. After `add_subparsers` has been called, the `add_subparser` method can be used
      instead of the `add_parser` method of the object returned by the `add_subparsers` call.
    - `add_subparser` takes takes the `parent_defaults` argument, which will set/change the defaults for the parent
      parser when that subparser is selected.
    - The `get_subparser` method will get the :class:`ArgumentParser` instance for an existing subparser on this parser
    - For any arguments defined both in this parser and one of its subparsers, the selected subparser default will
      override the main one.
    - Adds the `set_post_defaults` method. This works like the normal argparse `set_defaults` method, but all actions
      and subparsers will be run before any of these defaults are set.
    - Command shortening: If the command for a subparser is abbreviated unambiguously, it will still be accepted.
    - The add_argument `nargs` keyword argument supports a range of arguments, e.g. `"2-4"
    - If the `raise_errors` keyword argument to `parse_args` is True, a `ParserError` will be raised instead of sys.exit
    - If the `file` argument is given to `parse_args`, output will be printed there instead of sys.stdout or stderr
    """

    # These are created as a class attribute so that we can set it for parser and all subparsers at once
    file: Optional[IO[str]] = None
    do_help = True

    def __init__(self, **kwargs):
        """
        :param nested_namespace_name: When used as a subparser, options from this parser will be stored nested under
            this attribute name in the root parser's namespace
        """
        # Do this early, so even option processing stuff is caught
        if '--bugreport' in unicode_argv():
            self._debug_tb_callback()

        self.subparsers = None
        self.raise_errors = None
        add_help = kwargs.pop('add_help', True)
        kwargs['add_help'] = False
        ArgParser.__init__(self, **kwargs)
        if add_help:
            self.add_argument(
                '--help',
                '-h',
                action=HelpAction,
                dest=SUPPRESS,
                default=SUPPRESS,
                nargs=0,
                help='Show this help message and exit',
            )
        # Overwrite _SubparserAction with our custom one
        self.register('action', 'parsers', NestedSubparserAction)

        self.post_defaults = {}
        if kwargs.get('parents'):
            for parent in kwargs['parents']:
                if hasattr(parent, 'post_defaults'):
                    self.set_post_defaults(**parent.post_defaults)

    def add_argument(self, *args, **kwargs):
        if isinstance(kwargs.get('nargs'), str) and '-' in kwargs['nargs']:
            # Handle a custom range of arguments
            min, max = kwargs['nargs'].split('-')
            min, max = int(min), int(max)
            kwargs['action'] = required_length(min, max)
            # Make the usage string a bit better depending on whether the first argument is optional
            if min == 0:
                kwargs['nargs'] = '*'
            else:
                kwargs['nargs'] = '+'
        return super().add_argument(*args, **kwargs)

    def _print_message(self, message, file=None):
        """If a file argument was passed to `parse_args` make sure output goes there."""
        if self.file:
            file = self.file
        super()._print_message(message, file)

    def set_post_defaults(self, **kwargs):
        """Like set_defaults method, but these defaults will be defined after parsing instead of before."""
        self.post_defaults.update(kwargs)

        # if these defaults match any existing arguments, suppress
        # the previous default so that it can be filled after parsing
        for action in self._actions:
            if action.dest in kwargs:
                action.default = SUPPRESS

    def error(self, msg: str):
        raise ParserError(msg, self)

    def parse_args(
        self,
        args: List[str] = None,
        namespace: Namespace = None,
        raise_errors: bool = False,
        file: TextIO = None,
    ):  # pylint: disable=W0221
        """
        :param raise_errors: If this is true, errors will be raised as `ParserError`s instead of calling sys.exit
        """
        ArgumentParser.file = file
        try:
            return super().parse_args(args, namespace)
        except ParserError as e:
            if raise_errors:
                raise
            super(ArgumentParser, e.parser).error(e.message)
        finally:
            ArgumentParser.file = None

    def parse_known_args(
        self,
        args: List[str] = None,
        namespace: Namespace = None,
        do_help: bool = None,
    ):
        if args is None:
            # Decode all arguments to unicode before parsing
            args = unicode_argv()[1:]
        if namespace is None:
            namespace = ScopedNamespace()
        old_do_help = ArgumentParser.do_help
        if do_help is not None:
            ArgumentParser.do_help = do_help
        try:
            namespace, args = super().parse_known_args(args, namespace)
        finally:
            ArgumentParser.do_help = old_do_help

        # add any post defaults that aren't present
        for dest in self.post_defaults:
            if not hasattr(namespace, dest):
                setattr(namespace, dest, self.post_defaults[dest])

        return namespace, args

    def add_subparsers(self, **kwargs):
        """
        :param nested_namespaces: If True, options from subparsers will appear in nested namespace under the subparser
            name.
        """
        # Set the parser class so subparsers don't end up being an instance of a subclass, like CoreArgumentParser
        kwargs.setdefault('parser_class', ArgumentParser)
        kwargs.setdefault('required', True)
        self.subparsers = super().add_subparsers(**kwargs)
        return self.subparsers

    def add_subparser(self, name: str, **kwargs):
        """
        Adds a parser for a new subcommand and returns it.

        :param name: Name of the subcommand
        :param parent_defaults: Default argument values which should be supplied to the parent parser if this subparser
            is selected.
        """
        if not self.subparsers:
            raise TypeError('This parser does not have subparsers')
        result = self.subparsers.add_parser(name, **kwargs)
        return result

    def get_subparser(self, name: str, default=_UNSET):
        if not self.subparsers:
            raise TypeError('This parser does not have subparsers')
        p = self.subparsers.choices.get(name, default)
        if p is _UNSET:
            raise ValueError('%s is not an existing subparser name' % name)
        return p

    def _get_values(self, action, arg_strings):
        """Complete the full name for partial subcommands"""
        if action.nargs == PARSER and self.subparsers:
            subcommand = arg_strings[0]
            if subcommand not in self.subparsers.choices:
                matches = [x for x in self.subparsers.choices if x.startswith(subcommand)]
                if len(matches) == 1:
                    arg_strings[0] = matches[0]
        return super()._get_values(action, arg_strings)

    def _debug_tb_callback(self, *dummy):
        import cgitb

        cgitb.enable(format="text")


# This will hold just the arguments directly for Manager.
manager_parser = ArgumentParser(add_help=False)
manager_parser.add_argument(
    '-V',
    '--version',
    action=VersionAction,
    version=flexget.__version__,
    help='Print FlexGet version and exit.',
)
manager_parser.add_argument(
    '--test',
    action='store_true',
    dest='test',
    default=0,
    help='Verbose what would happen on normal execution.',
)
manager_parser.add_argument(
    '-c',
    dest='config',
    default='config.yml',
    help='Specify configuration file. Default: %(default)s',
)
manager_parser.add_argument(
    '--logfile',
    '-l',
    default='flexget.log',
    help='Specify a custom logfile name/location. '
    'Default: %(default)s in the config directory.',
)
manager_parser.add_argument(
    '--loglevel',
    '-L',
    metavar='LEVEL',
    help='Set the verbosity of the logger. Levels: %(choices)s',
    choices=['NONE', 'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'VERBOSE', 'DEBUG', 'TRACE'],
    type=str.upper,
)
manager_parser.set_post_defaults(loglevel='VERBOSE')
# This option is already handled above.
manager_parser.add_argument(
    '--bugreport',
    action='store_true',
    dest='debug_tb',
    help='Use this option to create a detailed bug report, '
    'note that the output might contain PRIVATE data, so edit that out',
)
manager_parser.add_argument(
    '--profile',
    metavar='OUTFILE',
    nargs='?',
    const='flexget.profile',
    help='Use the python profiler for this run to debug performance issues.',
)
manager_parser.add_argument('--debug', action=DebugAction, nargs=0, help=SUPPRESS)
manager_parser.add_argument('--debug-trace', action=DebugTraceAction, nargs=0, help=SUPPRESS)
manager_parser.add_argument('--debug-sql', action='store_true', default=False, help=SUPPRESS)
manager_parser.add_argument('--experimental', action='store_true', default=False, help=SUPPRESS)
manager_parser.add_argument('--ipc-port', type=int, help=SUPPRESS)
manager_parser.add_argument(
    '--cron',
    action=CronAction,
    default=False,
    nargs=0,
    help='use when executing FlexGet non-interactively: allows background '
    'maintenance to run, disables stdout and stderr output, reduces logging level',
)


class CoreArgumentParser(ArgumentParser):
    """
    The core argument parser, contains the manager arguments, command parsers, and plugin arguments.

    Warning: Only gets plugin arguments if instantiated after plugins have been loaded.

    """

    def __init__(self, **kwargs):
        kwargs.setdefault('parents', [manager_parser])
        kwargs.setdefault('prog', 'flexget')
        super().__init__(**kwargs)
        self.add_subparsers(
            title='commands', metavar='<command>', dest='cli_command', nested_namespaces=True
        )

        # The parser for the execute command
        exec_parser = self.add_subparser('execute', help='execute tasks now')
        exec_parser.add_argument(
            '--tasks',
            nargs='+',
            metavar='TASK',
            help='run only specified task(s), optionally using glob patterns ("tv-*"). '
            'matching is case-insensitive',
        )
        exec_parser.add_argument(
            '--learn',
            action='store_true',
            dest='learn',
            default=False,
            help='matches are not downloaded but will be skipped in the future',
        )
        exec_parser.add_argument('--profile', action='store_true', default=False, help=SUPPRESS)
        exec_parser.add_argument('--disable-phases', nargs='*', help=SUPPRESS)
        exec_parser.add_argument('--inject', nargs='+', action=InjectAction, help=SUPPRESS)
        # Plugins should respect these flags where appropriate
        exec_parser.add_argument(
            '--retry', action='store_true', dest='retry', default=False, help=SUPPRESS
        )
        exec_parser.add_argument(
            '--no-cache',
            action='store_true',
            dest='nocache',
            default=False,
            help='disable caches. works only in plugins that have explicit support',
        )

        daemonize_help = SUPPRESS
        if not sys.platform.startswith('win'):
            daemonize_help = 'causes process to daemonize after starting'

        # The parser for the daemon command
        daemon_parser = self.add_subparser(
            'daemon',
            parent_defaults={'loglevel': 'INFO'},
            help='run continuously, executing tasks according to schedules defined in config',
        )
        daemon_parser.add_subparsers(title='actions', metavar='<action>', dest='action')
        start_parser = daemon_parser.add_subparser('start', help='start the daemon')
        start_parser.add_argument('-d', '--daemonize', action='store_true', help=daemonize_help)
        start_parser.add_argument(
            '--autoreload-config',
            action='store_true',
            help='automatically reload the config from disk if the daemon detects any changes',
        )
        start_parser.add_argument(
            '--enable-tray-icon',
            action='store_true',
            dest='tray_icon',
            help='Enable the tray icon',
        )
        stop_parser = daemon_parser.add_subparser('stop', help='shutdown the running daemon')
        stop_parser.add_argument(
            '--wait',
            action='store_true',
            help='wait for all queued tasks to finish before stopping daemon',
        )
        daemon_parser.add_subparser('status', help='check if a daemon is running')
        daemon_parser.add_subparser(
            'reload-config', help='causes a running daemon to reload the config from disk'
        )

    def add_subparsers(self, **kwargs):
        # The subparsers should not be CoreArgumentParsers
        kwargs.setdefault('parser_class', ArgumentParser)
        return super().add_subparsers(**kwargs)

    def parse_args(self, *args, **kwargs):
        result = super().parse_args(*args, **kwargs)
        # Make sure we always have execute parser settings even when other commands called
        if not result.cli_command == 'execute':
            exec_options = get_parser('execute').parse_args([])
            if hasattr(result, 'execute'):
                exec_options.__dict__.update(result.execute.__dict__)
            result.execute = exec_options
        # Set the 'allow_manual' flag to True for any usage of the CLI
        setattr(result, 'allow_manual', True)
        return result
