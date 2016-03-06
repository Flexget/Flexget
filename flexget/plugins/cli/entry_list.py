from __future__ import unicode_literals, division, absolute_import

from argparse import ArgumentParser

from flexget import options
from flexget.event import event


def do_cli(manager, options):
    """Handle entry list subcommand"""
    if options.list_action == 'list':
        entry_list(options)
        return


def entry_list(options):
    pass


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('entry-list', do_cli, help='view and manage entry lists')
    name_parser = ArgumentParser(add_help=False)
    name_parser.add_argument('-l', '--list_name', metavar='list_name', help='name of entry list to operate on')
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='list_action')