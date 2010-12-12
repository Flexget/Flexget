import os
from optparse import OptionParser as OptParser, SUPPRESS_HELP
import flexget


class OptionParser(OptParser):
    """Contains all the options that both the core and webui should have"""

    def __init__(self, **kwargs):
        OptParser.__init__(self, **kwargs)

        self.version = flexget.__version__
        self.add_option('-V', '--version', action='version',
                        help='Print FlexGet version and exit.')
        self.add_option('--debug', action='callback', callback=self._debug_callback, dest='debug',
                        help=SUPPRESS_HELP)
        self.add_option('--debug-all', action='callback', callback=self._debug_callback, dest='debug_all',
                        help=SUPPRESS_HELP)
        self.add_option('--debug-perf', action='store_true', dest='debug_perf', default=False,
                        help=SUPPRESS_HELP)
        self.add_option('--loglevel', action='store', type='choice', default='info', dest='loglevel',
                        choices=['none', 'critical', 'error', 'warning', 'info', 'debug', 'debugall'],
                        help=SUPPRESS_HELP)
        self.add_option('--debug-sql', action='store_true', dest='debug_sql', default=False,
                        help=SUPPRESS_HELP)
        self.add_option('-c', action='store', dest='config', default='config.yml',
                        help='Specify configuration file. Default is config.yml')

    def _debug_callback(self, option, opt, value, parser):
        setattr(parser.values, option.dest, 1)
        if option.dest == 'debug':
            setattr(parser.values, 'loglevel', 'debug')
        elif option.dest == 'debug_all':
            setattr(parser.values, 'debug', 1)
            setattr(parser.values, 'loglevel', 'debugall')


class CoreOptionParser(OptionParser):
    """Contains all the options that should only be used when running without a ui"""

    def __init__(self, unit_test=False, **kwargs):
        OptionParser.__init__(self, **kwargs)

        self._unit_test = unit_test

        self.add_option('--log-start', action='store_true', dest='log_start', default=0,
                        help=SUPPRESS_HELP)
        self.add_option('--test', action='store_true', dest='test', default=0,
                        help='Verbose what would happend on normal execution.')
        self.add_option('--check', action='store_true', dest='validate', default=0,
                        help='Validate configuration file and print errors.')
        self.add_option('--learn', action='store_true', dest='learn', default=0,
                        help='Matches are not downloaded but will be skipped in the future.')
        self.add_option('--no-cache', action='store_true', dest='nocache', default=0,
                        help='Disable caches. Works only in plugins that have explicit support.')
        self.add_option('--reset', action='store_true', dest='reset', default=0,
                        help='Forgets everything that has been done and learns current matches.')
        self.add_option('--doc', action='store', dest='doc',
                        metavar='PLUGIN', help='Display plugin documentation. See also --plugins.')
        self.add_option('--cron', action='store_true', dest='quiet', default=False,
                        help='Disables stdout and stderr output, log file used. Reduces logging level slightly.')

        self.add_option('--experimental', action='store_true', dest='experimental', default=0,
                        help=SUPPRESS_HELP)
        self.add_option('--validate', action='store_true', dest='validate', default=False,
                        help=SUPPRESS_HELP)


        self.add_option('--migrate', action='store', dest='migrate', default=None,
                        help=SUPPRESS_HELP)

        # provides backward compatibility to --cron and -d
        self.add_option('-q', '--quiet', action='store_true', dest='quiet', default=False,
                        help=SUPPRESS_HELP)

    def parse_args(self, args=None):
        result = OptParser.parse_args(self, args or self._unit_test and ['flexget', '--reset'] or None)
        options = result[0]
        if options.test and options.learn:
            self.error('--test and --learn are mutually exclusive')

        if options.test and options.reset:
            self.error('--test and --reset are mutually exclusive')

        # reset and migrate should be executed with learn
        if (options.reset and not self._unit_test) or options.migrate:
            options.learn = True

        return result


class StoreErrorOptionParser(CoreOptionParser):
    """Parses options from a string instead of cli, doesn't exit on parser errors, stores them in error_msg attribute"""

    def __init__(self, baseparser):
        """Duplicates optios from another OptionParser"""
        CoreOptionParser.__init__(self, option_list=baseparser.option_list, conflict_handler="resolve")
        # Remove the options inappropriate to change mid-run
        self.remove_option('-h')
        self.remove_option('-V')
        self.remove_option('-c')
        self.error_msg = ''

    def parse_args(self, args):
        # Clear error message before parsing
        self.error_msg = ''
        # If args is a string, split it into an args list
        if isinstance(args, basestring):
            import shlex
            args = ['flexget'] + shlex.split(args.encode('utf-8'))
        return CoreOptionParser.parse_args(self, args)

    def error(self, msg):
        # Store error message for later
        self.error_msg = msg

    def get_help(self):
        # Remove the usage string from the help message
        result = self.format_help()
        first_newline = result.find('\n')
        result = result[first_newline:].lstrip('\n')
        return result


class UIOptionParser(OptionParser):
    """Contains the options for the webui"""

    def __init__(self):
        OptionParser.__init__(self)
        self.add_option('--port', action='store', type="int", dest='port', default=5050,
                        help='Run FlexGet webui in port [default: %default]')
        if os.name != 'nt':
            self.add_option('-d', '--daemonize', action='store_true', dest='daemon', default=False,
                            help='Causes webui to daemonize after starting')

        # enable flask autoreloading (development)
        self.add_option('--autoreload', action='store_true', dest='autoreload', default=False,
                        help=SUPPRESS_HELP)
