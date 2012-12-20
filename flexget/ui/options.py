from __future__ import unicode_literals, division, absolute_import
import os
from argparse import SUPPRESS
from flexget.options import ArgumentParser, CoreArgumentParser


class UIArgumentParser(ArgumentParser):
    """The UI options parser takes only ui options at the cli, but adds the default core options once cli is parsed"""

    def __init__(self, core_parser):
        # Set the conflict handler to resolve, so we can add core options as a parent later without errors
        super(UIArgumentParser, self).__init__(conflict_handler='resolve')
        self.core_parser = core_parser
        webui_group = self.add_argument_group('webui arguments')
        webui_group.add_argument('--port', action='store', type=int, dest='port', default=5050,
                        help='Run FlexGet webui in port [default: %(default)s]')
        if os.name != 'nt':
            webui_group.add_argument('-d', '--daemonize', action='store_true', dest='daemon', default=False,
                            help='Causes webui to daemonize after starting')

        # TODO: make a register_parser_option for webui and move these to authentication plugin?
        webui_group.add_argument('--no-auth', action='store_true', dest='no_auth',
                        help='Runs without authentication required (dangerous).')
        webui_group.add_argument('--username', action='store', dest='username',
                        help='Username needed to login [default: flexget]')
        webui_group.add_argument('--password', action='store', dest='password',
                        help='Password needed to login [default: flexget]')

        # enable flask autoreloading (development)
        webui_group.add_argument('--autoreload', action='store_true', dest='autoreload', default=False,
                        help=SUPPRESS)

    def parse_args(self, args=None, namespace=None):
        # Parse the arguments before adding all the core actions to make sure invalid options weren't used
        super(UIArgumentParser, self).parse_args(args, namespace)

        # Add core actions
        self._add_container_actions(self.core_parser)

        # Set the defaults from the core parser
        try:
            defaults = self.core_parser._defaults
        except AttributeError:
            pass
        else:
            self._defaults.update(defaults)

        # Now return the results with all of the options
        return super(UIArgumentParser, self).parse_args(args, namespace)


class StoreErrorArgumentParser(CoreArgumentParser):
    """Parses options from a string instead of cli, doesn't exit on parser errors, stores them in error_msg attribute"""

    def __init__(self, baseparser):
        """Duplicates options of a CoreArgumentParser for use mid-run"""
        super(StoreErrorArgumentParser, self).__init__(parents=[baseparser], conflict_handler='resolve')
        # Remove the options inappropriate to change mid-run
        # TODO: argparse doesn't seem to have a remove_argument method
        """self.remove_option('-h')
        self.remove_option('-V')
        self.remove_option('-c')
        self.remove_option('--doc')"""
        self.error_msg = ''

    def parse_args(self, args, namespace=None):
        # Clear error message before parsing
        self.error_msg = ''
        # If args is a string, split it into an args list
        if isinstance(args, basestring):
            import shlex
            args = shlex.split(args.encode('utf-8'))
        return super(StoreErrorArgumentParser, self).parse_args(args)

    def error(self, msg):
        # Store error message for later
        self.error_msg = msg

    def get_help(self):
        # Remove the usage string from the help message
        result = self.format_help()
        first_newline = result.find('\n')
        result = result[first_newline:].lstrip('\n')
        return result
