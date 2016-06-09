from __future__ import unicode_literals, division, absolute_import

from argparse import ArgumentParser, ArgumentTypeError

from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.plugins.list.series_list import SeriesListDBContainer as slDb


def do_cli(manager, options):
    """Handle series-list subcommand"""
    if options.list_action == 'all':
        series_list_lists(options)
        return

    if options.list_action == 'list':
        series_list_list(options)
        return


def series_list_lists(options):
    """ Show all series lists """
    lists = slDb.get_series_lists()
    console('Existing series lists:')
    console('-' * 20)
    for series_list in lists:
        console(series_list.name)


def series_list_list(options):
    """List series list"""
    with Session() as session:
        try:
            series_list = slDb.get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find series list with name {}'.format(options.list_name))
            return
        console('Series for list {}:'.format(options.list_name))
        console('-' * 79)
        for series in slDb.get_series_by_list_id(series_list.id, descending=True, session=session):
            title_string = '{} '.format(series.title)
            identifiers = '[' + ', '.join(
                '{}={}'.format(identifier.id_name, identifier.id_value) for identifier in series.ids) + ']'
            console(title_string + identifiers)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('series-list', do_cli, help='view and manage series lists')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='list_action')
    subparsers.add_parser('all', help='shows all existing series lists')

    list_name_parser = ArgumentParser(add_help=False)
    list_name_parser.add_argument('list_name', nargs='?', default='series', help='Name of series list to operate on')
    subparsers.add_parser('list', parents=[list_name_parser], help='list movies from a list')
