from __future__ import unicode_literals, division, absolute_import
import sys
from argparse import ArgumentParser as ArgParser, Action, ArgumentError, SUPPRESS, _VersionAction

import flexget
from flexget.utils.tools import console
from flexget.utils import requests
from flexget.event import event


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
        namespace.log_level = 'debug'


class DebugTraceAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True)
        namespace.debug = True
        namespace.log_level = 'trace'


class CronAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True)
        namespace.loglevel = 'info'


class ArgumentParser(ArgParser):
    """Overrides some default ArgumentParser behavior"""

    def __init__(self, **kwargs):
        # Do this early, so even option processing stuff is caught
        if '--bugreport' in sys.argv:
            self._debug_tb_callback()

        ArgParser.__init__(self, **kwargs)
        self.subparsers = None

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
        super(ArgumentParser, self).add_argument(*args, **kwargs)

    def parse_args(self, args=None, namespace=None):
        if args is None:
            # Decode all arguments to unicode before parsing
            args = [unicode(arg, sys.getfilesystemencoding()) for arg in sys.argv[1:]]
        return super(ArgumentParser, self).parse_args(args, namespace)

    def add_subparsers(self, **kwargs):
        result = super(ArgumentParser, self).add_subparsers(**kwargs)
        self.subparsers = result
        return result

    def add_subparser(self, name, **kwargs):
        if not self.subparsers:
            raise TypeError('This parser does not have subparsers')
        return self.subparsers.add_parser(name, **kwargs)

    def get_subparser(self, name, default=None):
        if not self.subparsers:
            raise TypeError('This parser does not have subparsers')
        return self.subparsers.choices.get(name, default=default)

    def _debug_tb_callback(self, *dummy):
        import cgitb
        cgitb.enable(format="text")


manager_parser = ArgumentParser(add_help=False)

manager_parser.add_argument('-V', '--version', action=VersionAction, help='Print FlexGet version and exit.')
manager_parser.add_argument('--test', action='store_true', dest='test', default=0,
                         help='Verbose what would happen on normal execution.')
manager_parser.add_argument('-c', dest='config', default='config.yml',
                         help='Specify configuration file. Default is config.yml')
manager_parser.add_argument('--logfile', default='flexget.log',
                         help='Specify a custom logfile name/location. '
                              'Default is flexget.log in the config directory.')
# TODO: rename dest to cron, since this does more than just quiet
manager_parser.add_argument('--cron', action=CronAction, dest='quiet', default=False, nargs=0,
                         help='Use when scheduling FlexGet with cron or other scheduler. Allows background '
                              'maintenance to run. Disables stdout and stderr output. Reduces logging level.')
# This option is already handled above.
manager_parser.add_argument('--bugreport', action='store_true', dest='debug_tb',
                         help='Use this option to create a detailed bug report, '
                              'note that the output might contain PRIVATE data, so edit that out')
# provides backward compatibility to --cron and -d
manager_parser.add_argument('-q', '--quiet', action=CronAction, dest='quiet', default=False, nargs=0,
                         help=SUPPRESS)
manager_parser.add_argument('--debug', action=DebugAction, nargs=0, help=SUPPRESS)
manager_parser.add_argument('--debug-trace', action=DebugTraceAction, nargs=0, help=SUPPRESS)
manager_parser.add_argument('--loglevel', default='verbose',
                         choices=['none', 'critical', 'error', 'warning', 'info', 'verbose', 'debug', 'trace'],
                         help=SUPPRESS)
manager_parser.add_argument('--debug-sql', action='store_true', default=False, help=SUPPRESS)
manager_parser.add_argument('--experimental', action='store_true', default=False, help=SUPPRESS)
manager_parser.add_argument('--del-db', action='store_true', dest='del_db', default=False, help=SUPPRESS)
manager_parser.add_argument('--profile', action='store_true', default=False, help=SUPPRESS)
manager_parser.add_argument('--log-start', action='store_true', dest='log_start', default=0, help=SUPPRESS)

core_parser = ArgumentParser(parents=[manager_parser])

core_subparsers = core_parser.add_subparsers(title='Commands', metavar='<command>', dest='subcommand')

exec_parser = core_subparsers.add_parser('exec', help='execute tasks now')

exec_parser.add_argument('--check', action='store_true', dest='validate', default=0,
                  help='Validate configuration file and print errors.')
exec_parser.add_argument('--learn', action='store_true', dest='learn', default=0,
                  help='Matches are not downloaded but will be skipped in the future.')
# Plugins should respect these flags where appropriate
exec_parser.add_argument('--retry', action='store_true', dest='retry', default=0, help=SUPPRESS)
exec_parser.add_argument('--no-cache', action='store_true', dest='nocache', default=0,
                  help='Disable caches. Works only in plugins that have explicit support.')


# TODO: CLI get rid of this and handle subcommands with events
def add_subparser(name, func, **kwargs):
    subparser = core_subparsers.add_parser(name, **kwargs)
    event('manager.subcommand.%s' % name)(func)
    return subparser
