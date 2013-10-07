from __future__ import unicode_literals, division, absolute_import
import copy
import random
import string
import sys

from argparse import ArgumentParser as ArgParser, Action, ArgumentError, SUPPRESS, _VersionAction, Namespace, PARSER

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


def get_defaults(command=None):
    if command:
        return getattr(get_parser(command).parse_args([]), command)
    return get_parser().parse_args([])


def register_command(command, callback, lock_required=False, **kwargs):
    subparser = get_parser().add_subparser(command, **kwargs)
    subparser.set_defaults(cli_command_callback=callback, lock_required=lock_required)
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
        namespace.loglevel = 'info'


# This makes the old --inject form forwards compatible
class InjectAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        new_value = getattr(namespace, self.dest, None) or []
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
        new_value.append(entry)
        setattr(namespace, self.dest, new_value)


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

    def __copy__(self):
        new = self.__class__()
        new.__dict__.update(self.__dict__)
        # Make copies of any nested namespaces
        for key, value in self.__dict__.iteritems():
            if key == '__parent__':
                continue
            if isinstance(value, ScopedNamespace):
                setattr(new, key, copy.copy(value))
        return new


class ArgumentParser(ArgParser):
    """Overrides some default ArgumentParser behavior"""

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
        ArgParser.__init__(self, **kwargs)

    def error(self, message):
        """Overridden error handler to print help message"""
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)

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
            result.dest = self.nested_namespace_name + '.' + result.dest
        return result

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            # Decode all arguments to unicode before parsing
            args = [unicode(arg, sys.getfilesystemencoding()) for arg in sys.argv[1:]]
        return super(ArgumentParser, self).parse_known_args(args, namespace or ScopedNamespace())

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

    def get_defaults(self):
        return self.parse_args([])

    def _debug_tb_callback(self, *dummy):
        import cgitb
        cgitb.enable(format="text")


# This will hold just the arguments directly for Manager. Webui needs this clean, to build its parser.
manager_parser = ArgumentParser(add_help=False)
manager_parser.add_argument('-V', '--version', action=VersionAction, help='Print FlexGet version and exit.')
manager_parser.add_argument('--test', action='store_true', dest='test', default=0,
                            help='Verbose what would happen on normal execution.')
manager_parser.add_argument('-c', dest='config', default='config.yml',
                            help='Specify configuration file. Default is config.yml')
manager_parser.add_argument('--logfile', default='flexget.log',
                            help='Specify a custom logfile name/location. '
                                 'Default is flexget.log in the config directory.')
# This option is already handled above.
manager_parser.add_argument('--bugreport', action='store_true', dest='debug_tb',
                            help='Use this option to create a detailed bug report, '
                                 'note that the output might contain PRIVATE data, so edit that out')
manager_parser.add_argument('--debug', action=DebugAction, nargs=0, help=SUPPRESS)
manager_parser.add_argument('--debug-trace', action=DebugTraceAction, nargs=0, help=SUPPRESS)
manager_parser.add_argument('--loglevel', default='verbose', help=SUPPRESS,
                            choices=['none', 'critical', 'error', 'warning', 'info', 'verbose', 'debug', 'trace'])
manager_parser.add_argument('--debug-sql', action='store_true', default=False, help=SUPPRESS)
manager_parser.add_argument('--experimental', action='store_true', default=False, help=SUPPRESS)
manager_parser.add_argument('--del-db', action='store_true', dest='del_db', default=False, help=SUPPRESS)


class CoreArgumentParser(ArgumentParser):
    """
    The core argument parser, contains the manager arguments, command parsers, and plugin arguments.

    Warning: Only gets plugin arguments if instantiated after plugins have been loaded.

    """
    def __init__(self, **kwargs):
        kwargs.setdefault('parents', [manager_parser])
        super(CoreArgumentParser, self).__init__(**kwargs)
        self.add_subparsers(title='Commands', metavar='<command>', dest='cli_command', scoped_namespaces=True)

        # The parser for the execute command
        exec_parser = self.add_subparser('execute', help='execute tasks now')
        exec_parser.set_defaults(lock_required=True)
        exec_parser.add_argument('--learn', action='store_true', dest='learn', default=0,
                                 help='Matches are not downloaded but will be skipped in the future.')
        exec_parser.add_argument('--cron', action=CronAction, default=False, nargs=0,
                                 help='Use when scheduling FlexGet with cron or other scheduler. Allows background '
                                      'maintenance to run. Disables stdout and stderr output. Reduces logging level.')
        exec_parser.add_argument('--loglevel', dest='exec_loglevel', help=SUPPRESS,
                                 choices=['none', 'critical', 'error', 'warning', 'info', 'verbose', 'debug', 'trace'])
        exec_parser.add_argument('--profile', action='store_true', default=False, help=SUPPRESS)
        exec_parser.add_argument('--disable-phases', nargs='*', help=SUPPRESS)
        exec_parser.add_argument('--inject', nargs='+', action=InjectAction, help=SUPPRESS)
        # Plugins should respect these flags where appropriate
        exec_parser.add_argument('--retry', action='store_true', dest='retry', default=0, help=SUPPRESS)
        exec_parser.add_argument('--no-cache', action='store_true', dest='nocache', default=0,
                                 help='Disable caches. Works only in plugins that have explicit support.')

        # The parser for the daemon command
        daemon_parser = self.add_subparser('daemon', help='Run continuously, executing tasks according to schedules '
                                                          'defined in config.')
        daemon_parser.add_argument('--ipc-port', type=int, default=29709, help='port which will be used for IPC')
        # TODO: 1.2 Make this work
        daemon_parser.set_defaults(loglevel='info')

    def add_subparsers(self, **kwargs):
        # The subparsers should not be CoreArgumentParsers
        kwargs.setdefault('parser_class', ArgumentParser)
        return super(CoreArgumentParser, self).add_subparsers(**kwargs)

    def parse_args(self, args=None, namespace=None):
        result = super(CoreArgumentParser, self).parse_args(args=args, namespace=namespace)
        # Make sure we always have execute parser settings even when other commands called
        if not result.cli_command == 'execute':
            exec_options = get_defaults('execute')
            if hasattr(result, 'execute'):
                exec_options.__dict__.update(result.execute.__dict__)
            result.execute = exec_options
        return result
