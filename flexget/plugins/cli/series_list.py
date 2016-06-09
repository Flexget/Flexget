from __future__ import unicode_literals, division, absolute_import

from argparse import ArgumentParser, ArgumentTypeError

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.plugins.list.series_list import SeriesListDBContainer as slDb


def do_cli(manager, options):
    """Handle series-list subcommand"""
    if options.list_action == 'all':
        series_list_lists(options)
        return


def series_list_lists(options):
    """ Show all movie lists """
    lists = slDb.get_series_lists()
    console('Existing series lists:')
    console('-' * 20)
    for series_list in lists:
        console(series_list.name)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('series-list', do_cli, help='view and manage series lists')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='list_action')
    subparsers.add_parser('all', help='shows all existing series lists')
