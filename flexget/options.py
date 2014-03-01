from __future__ import unicode_literals, division, absolute_import
import copy
import pkg_resources
import random
import socket
import string
import sys
from argparse import (ArgumentParser as ArgParser, Action, ArgumentError, SUPPRESS, PARSER, REMAINDER, _VersionAction,
                      Namespace, ArgumentTypeError)

import flexget
from flexget.utils.tools import console
from flexget.utils import requests
from flexget.entry import Entry
from flexget.event import fire_event


_UNSET = object()

core_parser = None


def get_parser(command=None):
    global core_parser
    if not core_parser:
        core_parser = CoreArgumentParser()
        # Add all plugin options to the parser
        fire_event('options.register')
    if command:
        return core_parser.get_subparser(command)
    return core_parser


def register_command(command, callback, **kwargs):
    """
    Register a callback function to be executed when flexget is launched with the given `command`.

    :param command: The command being defined.
    :param callback: Callback function executed when this command is invoked from the CLI. Should take manager instance
        and parsed argparse namespace as parameters.
    :param kwargs: Other keyword arguments will be passed to the :class:`arparse.ArgumentParser` constructor
    :returns: An :class:`argparse.ArgumentParser` instance ready to be configured with the options for this command.
    """
    subparser = get_parser().add_subparser(command, **kwargs)
    subparser.set_defaults(cli_command_callback=callback)
    return subparser


def required_length(nmin, nmax):
    """Generates a custom Action to validate an arbitrary range of arguments."""
    class RequiredLength(Action):
        def __call__(self, parser, args, values, option_string=None):
            if not nmin <= len(values) <= nmax:
                raise ArgumentError(self, 'requires between %s and %s arguments' % (nmin, nmax))
            setattr(args, self.dest, values)
    return RequiredLength


class VersionAction(_VersionAction):
    """
    Action to print the current version.
    Also attempts to get more information from git describe if on git checkout.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        self.version = flexget.__version__
        # Print the version number
        console('%s' % self.version)
        if self.version == '{git}':
            console('To check the latest released version you have run:')
            console('`git fetch --tags` then `git describe`')
        else:
            # Check for latest version from server
            try:
                page = requests.get('http://download.flexget.com/latestversion')
            except requests.RequestException:
                console('Error getting latest version number from download.flexget.com')
            else:
                ver = page.text.strip()
                if self.version == ver:
                    console('You are on the latest release.')
                else:
                    console('Latest release: %s' % ver)
        parser.exit()


class DebugAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True)
        namespace.loglevel = 'debug'


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
            namespace.loglevel = 'info'


# This makes the old --inject form forwards compatible
class InjectAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        kwargs = {'title': values.pop(0)}
        if values:
            kwargs['url'] = values.pop(0)
        else:
            kwargs['url'] = 'http://localhost/inject/%s' % ''.join(random.sample(string.letters + string.digits, 30))
        if 'force' in [v.lower() for v in values]:
            kwargs['immortal'] = True
        entry = Entry(**kwargs)
        if 'accept' in [v.lower() for v in values]:
            entry.accept(reason='accepted by --inject')
        setattr(namespace, self.dest, [entry])


class ParseExtrasAction(Action):
    """This action will take extra arguments, and parser them with a different parser."""
    def __init__(self, option_strings, parser, help=None, metavar=None, dest=None, required=False):
        if metavar is None:
            metavar = '<%s arguments>' % parser.prog
        if help is None:
            help = 'arguments for the `%s` command are allowed here' % parser.prog
        self._parser = parser
        super(ParseExtrasAction, self).__init__(option_strings=option_strings, dest=SUPPRESS, help=help,
                                                metavar=metavar, nargs=REMAINDER, required=required)

    def __call__(self, parser, namespace, values, option_string=None):
        namespace, extras = self._parser.parse_known_args(values, namespace)
        if extras:
            parser.error('unrecognized arguments: %s' % ' '.join(extras))


class ScopedNamespace(Namespace):
    def __init__(self, **kwargs):
        super(ScopedNamespace, self).__init__(**kwargs)
        self.__parent__ = None

    def __getattr__(self, key):
        if '.' in key:
            scope, key = key.split('.', 1)
            return getattr(getattr(self, scope), key)

        if self.__parent__:
            return getattr(self.__parent__, key)
        raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, key))

    def __setattr__(self, key, value):
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
        return (i for i in self.__dict__.iteritems() if i[0] != '__parent__')

    def __copy__(self):
        new = self.__class__()
        new.__dict__.update(self.__dict__)
        # Make copies of any nested namespaces
        for key, value in self:
            if isinstance(value, ScopedNamespace):
                setattr(new, key, copy.copy(value))
        return new


class ParserError(Exception):
    def __init__(self, message, parser):
        self.message = message
        self.parser = parser

    def __unicode__(self):
        return self.message

    def __repr__(self):
        return 'ParserError(%s, %s)' % self.message, self.parser


class ArgumentParser(ArgParser):
    """
    Mimics the default :class:`argparse.ArgumentParser` class, with a few distinctions, mostly to ease subparser usage:

    - Adds the `add_subparser` method. After `add_subparsers` has been called, the `add_subparser` method can be used
      instead of the `add_parser` method of the object returned by the `add_subparsers` call.
    - If `add_subparser` is called with the `scoped_namespace` kwarg, all subcommand options will be stored in a
      nested namespace scope based on the command name for this subparser
    - The `get_subparser` method will get the :class:`ArgumentParser` instance for an existing subparser on this parser
    - For any arguments defined both in this parser and one of its subparsers, the selected subparser default will
      override the main one.
    - Command shortening: If the command for a subparser is abbreviated unambiguously, it will still be accepted.
    - The add_argument `nargs` keyword argument supports a range of arguments, e.g. `"2-4"
    - If the `raise_errors` keyword argument to `parse_args` is True, a `ValueError` will be raised instead of sys.exit
    """

    def __init__(self, nested_namespace_name=None, **kwargs):
        """
        :param nested_namespace_name: When used as a subparser, options from this parser will be stored nested under
            this attribute name in the root parser's namespace
        """
        # Do this early, so even option processing stuff is caught
        if '--bugreport' in sys.argv:
            self._debug_tb_callback()

        self.subparsers = None
        self.nested_namespace_name = nested_namespace_name
        self.raise_errors = None
        ArgParser.__init__(self, **kwargs)

    def add_argument(self, *args, **kwargs):
        if isinstance(kwargs.get('nargs'), basestring) and '-' in kwargs['nargs']:
            # Handle a custom range of arguments
            min, max = kwargs['nargs'].split('-')
            min, max = int(min), int(max)
            kwargs['action'] = required_length(min, max)
            # Make the usage string a bit better depending on whether the first argument is optional
            if min == 0:
                kwargs['nargs'] = '*'
            else:
                kwargs['nargs'] = '+'
        result = super(ArgumentParser, self).add_argument(*args, **kwargs)
        if self.nested_namespace_name:
            # If metavar hasn't already been set, set it without the nested scope name
            if not result.metavar:
                result.metavar = result.dest
                if result.option_strings and result.option_strings[0].startswith('-'):
                    result.metavar = result.dest.upper()
            result.dest = self.nested_namespace_name + '.' + result.dest
        return result

    def print_help(self, file=None):
        self.restore_defaults()
        super(ArgumentParser, self).print_help(file)

    def stash_defaults(self):
        """Remove all the defaults and store them in a temporary location."""
        self.real_defaults, self._defaults = self._defaults, {}
        for action in self._actions:
            action.real_default, action.default = action.default, SUPPRESS

    def restore_defaults(self):
        """Restore all stashed defaults."""
        if hasattr(self, 'real_defaults'):
            self._defaults = self.real_defaults
            del self.real_defaults
        for action in self._actions:
            if hasattr(action, 'real_default'):
                action.default = action.real_default
                del action.real_default

    def error(self, msg):
        raise ParserError(msg, self)

    def parse_args(self, args=None, namespace=None, raise_errors=False):
        """
        :param raise_errors: If this is true, errors will be raised as `ParserError`s instead of calling sys.exit
        """
        try:
            return super(ArgumentParser, self).parse_args(args, namespace)
        except ParserError as e:
            if raise_errors:
                raise
            sys.stderr.write('error: %s\n' % e.message)
            e.parser.print_help()
            sys.exit(2)

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            # Decode all arguments to unicode before parsing
            args = [unicode(arg, sys.getfilesystemencoding()) for arg in sys.argv[1:]]
        # Remove all of our defaults, to give subparsers and custom actions first priority at setting them
        self.stash_defaults()
        try:
            namespace, _ = super(ArgumentParser, self).parse_known_args(args, namespace or ScopedNamespace())
        except ParserError:
            pass
        finally:
            # Restore the defaults
            self.restore_defaults()
        # Parse again with subparser and custom action defaults already in the namespace
        return super(ArgumentParser, self).parse_known_args(args, namespace)

    def add_subparsers(self, scoped_namespaces=False, **kwargs):
        # Set the parser class so subparsers don't end up being an instance of a subclass, like CoreArgumentParser
        kwargs.setdefault('parser_class', ArgumentParser)
        self.subparsers = super(ArgumentParser, self).add_subparsers(**kwargs)
        self.subparsers.scoped_namespaces = scoped_namespaces
        return self.subparsers

    def add_subparser(self, name, **kwargs):
        """
        Adds a parser for a new subcommand and returns it.

        :param name: Name of the subcommand
        :param require_lock: Whether this subcommand should require a database lock
        """
        if not self.subparsers:
            raise TypeError('This parser does not have subparsers')
        if self.subparsers.scoped_namespaces:
            kwargs.setdefault('nested_namespace_name', name)
        result = self.subparsers.add_parser(name, **kwargs)
        if self.subparsers.scoped_namespaces:
            result.set_defaults(**{name: ScopedNamespace()})
        return result

    def get_subparser(self, name, default=_UNSET):
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
        return super(ArgumentParser, self)._get_values(action, arg_strings)

    def _debug_tb_callback(self, *dummy):
        import cgitb
        cgitb.enable(format="text")


# This will hold just the arguments directly for Manager. Webui needs this clean, to build its parser.
manager_parser = ArgumentParser(add_help=False)
manager_parser.add_argument('-V', '--version', action=VersionAction, help='Print FlexGet version and exit.')
manager_parser.add_argument('--test', action='store_true', dest='test', default=0,
                            help='Verbose what would happen on normal execution.')
manager_parser.add_argument('-c', dest='config', default='config.yml',
                            help='Specify configuration file. Default: %(default)s')
manager_parser.add_argument('--logfile', '-l', default='flexget.log',
                            help='Specify a custom logfile name/location. '
                                 'Default: %(default)s in the config directory.')
manager_parser.add_argument('--loglevel', '-L', metavar='LEVEL',
                            default='verbose',
                            help='Set the verbosity of the logger. Levels: %(choices)s',
                            choices=['none', 'critical', 'error', 'warning', 'info', 'verbose', 'debug', 'trace'])
# This option is already handled above.
manager_parser.add_argument('--bugreport', action='store_true', dest='debug_tb',
                            help='Use this option to create a detailed bug report, '
                                 'note that the output might contain PRIVATE data, so edit that out')
manager_parser.add_argument('--profile', metavar='OUTFILE', nargs='?', const='flexget.profile',
                            help='Use the python profiler for this run to debug performance issues.')
manager_parser.add_argument('--debug', action=DebugAction, nargs=0, help=SUPPRESS)
manager_parser.add_argument('--debug-trace', action=DebugTraceAction, nargs=0, help=SUPPRESS)
manager_parser.add_argument('--debug-sql', action='store_true', default=False, help=SUPPRESS)
manager_parser.add_argument('--experimental', action='store_true', default=False, help=SUPPRESS)
manager_parser.add_argument('--ipc-port', type=int, help=SUPPRESS)


class CoreArgumentParser(ArgumentParser):
    """
    The core argument parser, contains the manager arguments, command parsers, and plugin arguments.

    Warning: Only gets plugin arguments if instantiated after plugins have been loaded.

    """
    def __init__(self, **kwargs):
        kwargs.setdefault('parents', [manager_parser])
        kwargs.setdefault('prog', 'flexget')
        super(CoreArgumentParser, self).__init__(**kwargs)
        self.add_subparsers(title='commands', metavar='<command>', dest='cli_command', scoped_namespaces=True)

        # The parser for the execute command
        exec_parser = self.add_subparser('execute', help='execute tasks now')
        exec_parser.add_argument('--tasks', nargs='+', metavar='TASK',
                                 help='run only specified task(s), optionally using glob patterns ("tv-*"). '
                                      'matching is case-insensitive')
        exec_parser.add_argument('--learn', action='store_true', dest='learn', default=False,
                                 help='matches are not downloaded but will be skipped in the future')
        exec_parser.add_argument('--cron', action=CronAction, default=False, nargs=0,
                                 help='use when scheduling FlexGet with cron or other scheduler: allows background '
                                      'maintenance to run, disables stdout and stderr output, reduces logging level')
        exec_parser.add_argument('--profile', action='store_true', default=False, help=SUPPRESS)
        exec_parser.add_argument('--disable-phases', nargs='*', help=SUPPRESS)
        exec_parser.add_argument('--inject', nargs='+', action=InjectAction, help=SUPPRESS)
        # Plugins should respect these flags where appropriate
        exec_parser.add_argument('--retry', action='store_true', dest='retry', default=False, help=SUPPRESS)
        exec_parser.add_argument('--no-cache', action='store_true', dest='nocache', default=False,
                                 help='disable caches. works only in plugins that have explicit support')

        daemonize_help = SUPPRESS
        if not sys.platform.startswith('win'):
            daemonize_help = 'causes process to daemonize after starting'

        # The parser for the daemon command
        daemon_parser = self.add_subparser('daemon', help='run continuously, executing tasks according to schedules '
                                                          'defined in config')
        daemon_parser.add_subparsers(title='actions', metavar='<action>', dest='action')
        start_parser = daemon_parser.add_subparser('start', help='start the daemon')
        start_parser.add_argument('-d', '--daemonize', action='store_true', help=daemonize_help)
        daemon_parser.add_subparser('stop', help='shutdown the running daemon')
        daemon_parser.add_subparser('status', help='check if a daemon is running')
        daemon_parser.add_subparser('reload', help='causes a running daemon to reload the config from disk')
        daemon_parser.set_defaults(loglevel='info')

        # The parser for the webui
        # Hide the webui command if deps aren't available
        webui_kwargs = {}
        try:
            pkg_resources.require('flexget[webui]')
            webui_kwargs['help'] = 'run continuously, with a web interface to configure and interact with the daemon'
        except pkg_resources.DistributionNotFound:
            pass
        webui_parser = self.add_subparser('webui', **webui_kwargs)

        def ip_type(value):
            try:
                socket.inet_aton(value)
            except socket.error:
                raise ArgumentTypeError('must be a valid ip address to bind to')
            return value

        webui_parser.add_argument('--bind', type=ip_type, default='0.0.0.0', metavar='IP',
                                  help='IP address to bind to when serving the web interface [default: %(default)s]')
        webui_parser.add_argument('--port', type=int, default=5050,
                                  help='run FlexGet webui on port [default: %(default)s]')
        webui_parser.add_argument('-d', '--daemonize', action='store_true', help=daemonize_help)

        # TODO: move these to authentication plugin?
        webui_parser.add_argument('--no-auth', action='store_true',
                                  help='runs without authentication required (dangerous)')
        webui_parser.add_argument('--no-local-auth', action='store_true',
                                  help='runs without any authentication required when accessed from localhost')
        webui_parser.add_argument('--username', help='username needed to login [default: flexget]')
        webui_parser.add_argument('--password', help='password needed to login [default: flexget]')

        # enable flask autoreloading (development)
        webui_parser.add_argument('--autoreload', action='store_true', help=SUPPRESS)
        webui_parser.set_defaults(loglevel='info')

    def add_subparsers(self, **kwargs):
        # The subparsers should not be CoreArgumentParsers
        kwargs.setdefault('parser_class', ArgumentParser)
        return super(CoreArgumentParser, self).add_subparsers(**kwargs)

    def parse_args(self, *args, **kwargs):
        result = super(CoreArgumentParser, self).parse_args(*args, **kwargs)
        # Make sure we always have execute parser settings even when other commands called
        if not result.cli_command == 'execute':
            exec_options = get_parser('execute').parse_args([]).execute
            if hasattr(result, 'execute'):
                exec_options.__dict__.update(result.execute.__dict__)
            result.execute = exec_options
        return result
