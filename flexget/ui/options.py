from __future__ import unicode_literals, division, absolute_import
import os
from argparse import SUPPRESS
from flexget.options import ArgumentParser, manager_parser


webui_parser = ArgumentParser(parents=[manager_parser])

webui_group = webui_parser.add_argument_group('webui arguments')
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


class RaiseErrorArgumentParser(ArgumentParser):
    """Parses options from a string instead of cli, doesn't exit on parser errors, raises a ValueError instead"""

    def __init__(self, **kwargs):
        kwargs.setdefault('add_help', False)
        kwargs.setdefault('usage', SUPPRESS)
        super(RaiseErrorArgumentParser, self).__init__(**kwargs)

    def parse_args(self, args, namespace=None):
        # If args is a string, split it into an args list
        if isinstance(args, basestring):
            import shlex
            args = shlex.split(args)
        return super(RaiseErrorArgumentParser, self).parse_args(args)

    def error(self, msg):
        raise ValueError(msg)
