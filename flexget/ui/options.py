import os
from optparse import SUPPRESS_HELP
from flexget.options import OptionParser, CoreOptionParser


class UIOptionParser(OptionParser):
    """The UI options parser takes only ui options at the cli, but adds the default core options once cli is parsed"""

    def __init__(self, core_parser):
        OptionParser.__init__(self)
        self.core_parser = core_parser
        self.add_option('--port', action='store', type="int", dest='port', default=5050,
                        help='Run FlexGet webui in port [default: %default]')
        if os.name != 'nt':
            self.add_option('-d', '--daemonize', action='store_true', dest='daemon', default=False,
                            help='Causes webui to daemonize after starting')

        # TODO: make a register_parser_option for webui and move these to authentication plugin?
        self.add_option('--no-auth', action='store_true', dest='no_auth',
                        help='Runs with no username/password needed.')
        self.add_option('--username', action='store', dest='username',
                        help='Changes the username needed to connect.')
        self.add_option('--password', action='store', dest='password',
                        help='Changes the password needed to connect.')

        # enable flask autoreloading (development)
        self.add_option('--autoreload', action='store_true', dest='autoreload', default=False,
                        help=SUPPRESS_HELP)

    def check_values(self, values, args):
        """Adds the options from the core parser once cli has been parsed"""
        core_values = self.core_parser.get_default_values()
        core_values._update_loose(values.__dict__)
        self.values = core_values
        return (self.values, args)


class StoreErrorOptionParser(CoreOptionParser):
    """Parses options from a string instead of cli, doesn't exit on parser errors, stores them in error_msg attribute"""

    def __init__(self, baseparser):
        """Duplicates options of a CoreOptionParser for use mid-run"""
        CoreOptionParser.__init__(self, option_list=baseparser.option_list, conflict_handler="resolve")
        # Remove the options inappropriate to change mid-run
        self.remove_option('-h')
        self.remove_option('-V')
        self.remove_option('-c')
        self.remove_option('--doc')
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
