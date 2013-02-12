from __future__ import unicode_literals, division, absolute_import
import sys
from argparse import ArgumentParser as ArgParser, Action, ArgumentError, SUPPRESS, _VersionAction

import flexget
from flexget.utils.tools import console
from flexget.utils import requests


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


class ArgumentParser(ArgParser):
    """Contains all the options that both the core and webui should have"""

    def __init__(self, **kwargs):
        # Do this early, so even option processing stuff is caught
        if '--bugreport' in sys.argv:
            self._debug_tb_callback()

        ArgParser.__init__(self, **kwargs)

        self.add_argument('-V', '--version', action=VersionAction, version=flexget.__version__,
                          help='Print FlexGet version and exit.')
        # This option is already handled above.
        self.add_argument('--bugreport', action='store_true', dest='debug_tb',
                          help='Use this option to create a detailed bug report, '
                               'note that the output might contain PRIVATE data, so edit that out')
        self.add_argument('--logfile', default='flexget.log',
                          help='Specify a custom logfile name/location. '
                               'Default is flexget.log in the config directory.')
        self.add_argument('--debug', action='store_true', dest='debug',
                          help=SUPPRESS)
        self.add_argument('--debug-trace', action='store_true', dest='debug_trace',
                          help=SUPPRESS)
        self.add_argument('--loglevel', default='verbose',
                          choices=['none', 'critical', 'error', 'warning', 'info', 'verbose', 'debug', 'trace'],
                          help=SUPPRESS)
        self.add_argument('--debug-sql', action='store_true', default=False,
                          help=SUPPRESS)
        self.add_argument('-c', dest='config', default='config.yml',
                          help='Specify configuration file. Default is config.yml')
        self.add_argument('--experimental', action='store_true', default=False,
                          help=SUPPRESS)
        self.add_argument('--del-db', action='store_true', dest='del_db', default=False,
                          help=SUPPRESS)
        self.add_argument('--profile', action='store_true', default=False, help=SUPPRESS)

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
            args = [unicode(arg, sys.getfilesystemencoding()) for arg in sys.argv[1:]]
        args = super(ArgumentParser, self).parse_args(args, namespace)
        if args.debug_trace:
            args.debug = True
            args.loglevel = 'trace'
        elif args.debug:
            args.loglevel = 'debug'
        return args

    def _debug_tb_callback(self, *dummy):
        import cgitb
        cgitb.enable(format="text")


class CoreArgumentParser(ArgumentParser):
    """Contains all the options that should only be used when running without a ui"""

    def __init__(self, unit_test=False, **kwargs):
        ArgumentParser.__init__(self, **kwargs)

        self._unit_test = unit_test

        self.add_argument('--log-start', action='store_true', dest='log_start', default=0,
                          help=SUPPRESS)
        self.add_argument('--test', action='store_true', dest='test', default=0,
                          help='Verbose what would happen on normal execution.')
        self.add_argument('--check', action='store_true', dest='validate', default=0,
                          help='Validate configuration file and print errors.')
        self.add_argument('--learn', action='store_true', dest='learn', default=0,
                          help='Matches are not downloaded but will be skipped in the future.')
        self.add_argument('--no-cache', action='store_true', dest='nocache', default=0,
                          help='Disable caches. Works only in plugins that have explicit support.')
        self.add_argument('--reset', action='store_true', dest='reset', default=0,
                          help='DANGEROUS. Obliterates the database and runs with learn '
                               'in order to to regain useful state.')
        # TODO: rename dest to cron, since this does more than just quiet
        self.add_argument('--cron', action='store_true', dest='quiet', default=False,
                          help='Disables stdout and stderr output, log file used. Reduces logging level slightly.')
        self.add_argument('--db-cleanup', action='store_true', dest='db_cleanup', default=False,
                          help='Forces the database cleanup event to run right now.')

        # Plugins should respect this flag and retry where appropriate
        self.add_argument('--retry', action='store_true', dest='retry', default=0, help=SUPPRESS)

        self.add_argument('--validate', action='store_true', dest='validate', default=False,
                          help=SUPPRESS)

        self.add_argument('--migrate', action='store', dest='migrate', default=None,
                          help=SUPPRESS)

        # provides backward compatibility to --cron and -d
        self.add_argument('-q', '--quiet', action='store_true', dest='quiet', default=False,
                          help=SUPPRESS)

    def parse_args(self, args=None, namespace=None):
        args = super(CoreArgumentParser, self).parse_args(args or self._unit_test and ['--reset'] or None, namespace)

        if args.test and (args.learn or args.reset):
            self.error('--test and %s are mutually exclusive' % ('--learn' if args.learn else '--reset'))

        # reset and migrate should be executed with learn
        if (args.reset and not self._unit_test) or args.migrate:
            args.learn = True

        # Lower the log level when executed with --cron
        if args.quiet:
            args.loglevel = 'info'

        return args
