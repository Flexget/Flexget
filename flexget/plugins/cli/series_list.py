from __future__ import unicode_literals, division, absolute_import

import re
from argparse import ArgumentParser, ArgumentTypeError

from sqlalchemy.orm.exc import NoResultFound

from flexget import options, plugin
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.utils import qualities
from flexget.config_schema import parse_interval
from flexget.plugins.list.series_list import SeriesListList, SeriesListDBContainer as slDb, SeriesList, get_db_series
from flexget.plugins.filter.series import FilterSeriesBase

SETTINGS_SCHEMA = FilterSeriesBase().settings_schema
SERIES_ATTRIBUTES = SETTINGS_SCHEMA['properties']


def supported_ids():
    # Return a list of supported series identifier as registered via their plugins
    ids = []
    for p in plugin.get_plugins(group='series_metainfo'):
        ids.append(p.instance.series_identifier())
    return ids


class SeriesListType(object):
    """ Container class that hold several custom argparse types"""

    @staticmethod
    def regex_type(value):
        """ Custom argparse type that validates regex"""
        try:
            re.compile(value)
        except re.error:
            raise ArgumentTypeError('value {} is not a valid regexp'.format(value))
        return value

    @staticmethod
    def quality_req_type(value):
        """ Custom argparse type that validates Quality"""
        try:
            qualities.Requirements(value)
        except ValueError as e:
            raise ArgumentTypeError(e)
        return value

    @staticmethod
    def interval_type(value):
        """ Custom argparse type that validates Interval"""
        try:
            parse_interval(value)
        except (ValueError, TypeError) as e:
            raise ArgumentTypeError(e)
        return value

    @staticmethod
    def episode_identifier(value):
        result = re.match(r'(?i)^S\d{2,4}E\d{2,3}$', value)
        if not result:
            raise ArgumentTypeError('Value {} does not match identifier format of `SxxEyy`'.format(value))
        return value

    @staticmethod
    def date_identifier(value):
        result = re.match(r'^\d{4}-\d{2}-\d{2}$', value)
        if not result:
            raise ArgumentTypeError('Value {} does not match identifier format of `YYYY-MM-DD`'.format(value))
        return value

    @staticmethod
    def sequence_identifier(value):
        try:
            if int(value) < 0:
                ArgumentTypeError('Value {} must be an integer higher than 0'.format(value))
        except ValueError:
            raise ArgumentTypeError('Value {} must be an integer higher than 0'.format(value))
        return value

    @staticmethod
    def series_list_keyword_type(identifier):
        if identifier.count('=') != 1:
            raise ArgumentTypeError('Received identifier in wrong format: %s, '
                                    ' should be in keyword format like `tvdb_id=1234567`' % identifier)
        name, value = identifier.split('=', 2)
        if name not in supported_ids():
            raise ArgumentTypeError(
                'Received unsupported identifier ID %s. Should be one of %s' % (identifier, ' ,'.join(supported_ids())))
        return {name: value}


def build_data_dict(options):
    """ Converts options to a recognizable data type for series adding/matching"""
    data = {'series_name': options.series_title}
    for attribute in SERIES_ATTRIBUTES:
        if attribute == 'set':
            continue
        data[attribute] = getattr(options, attribute)
    if options.identifiers:
        for identifier in options.identifiers:
            if identifier in supported_ids():
                for k, v in identifier.items():
                    data[k] = v
    return data


def do_cli(manager, options):
    """Handle series-list subcommand"""
    if options.list_action == 'all':
        series_list_lists(options)
        return

    if options.list_action == 'list':
        series_list_list(options)
        return

    if options.list_action == 'add':
        series_list_add(options)
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


def series_list_add(options):
    """ Add series to the series list """
    with Session() as session:
        try:
            series_list = slDb.get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find series list with name {}, creating'.format(options.list_name))
            series_list = SeriesListList(name=options.list_name)
        session.merge(series_list)
        data = build_data_dict(options)
        series = SeriesList(options.list_name, session=session).find_entry(data, session=session)
        if series:
            console('Series with title {} already exist'.format(options.series_title))
            return
        series = get_db_series(data)
        series.list_id = series_list.id
        session.add(series)
        console('Successfully added series {} to list {}'.format(series.title, series_list.name))


@event('options.register')
def register_parser_arguments():
    series_parser = ArgumentParser(add_help=False)
    series_parser.add_argument('series_title', metavar='series-title',
                               help="Title of the series. Should include country code if relevant")

    list_name_parser = ArgumentParser(add_help=False)
    list_name_parser.add_argument('list_name', nargs='?', default='series',
                                  help='Name of series list to operate on. Default is `series`')

    parser = options.register_command('series-list', do_cli, help='View and manage series lists')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='list_action')
    subparsers.add_parser('all', help='Shows all existing series lists')
    subparsers.add_parser('list', parents=[list_name_parser], help='List movies from a list')
    add_subparser = subparsers.add_parser('add', parents=[list_name_parser, series_parser],
                                          help='Add a series to a list')
    add_subparser.add_argument('--path', help='Set path field for this series')
    add_subparser.add_argument('--alternate-name', nargs='+', help='Alternate series name(s)')
    add_subparser.add_argument('--name-regexp', nargs='+', type=SeriesListType.regex_type,
                               help='Manually specify regexp(s) that matches to series name')
    add_subparser.add_argument('--ep-regexp', nargs='+', type=SeriesListType.regex_type,
                               help='Manually specify regexp(s) that matches to episode, season numbering')
    add_subparser.add_argument('--date-regexp', nargs='+', type=SeriesListType.regex_type, help='Date regexp')
    add_subparser.add_argument('--sequence-regexp', nargs='+', type=SeriesListType.regex_type, help='Sequence regexp')
    add_subparser.add_argument('--id-regexp', nargs='+', type=SeriesListType.regex_type,
                               help='Manually specify regexp(s) that matches to series identifier (numbering)')
    add_subparser.add_argument('--date-yearfirst', type=bool, help='Parse year first')
    add_subparser.add_argument('--date-dayfirst', type=bool, help='Parse date first')
    add_subparser.add_argument('--quality', type=SeriesListType.quality_req_type, help='Required quality')
    add_subparser.add_argument('--qualities', type=SeriesListType.quality_req_type, nargs='+',
                               help='Download all listed qualities when they become available')
    add_subparser.add_argument('--timeframe', type=SeriesListType.interval_type,
                               help='Wait given amount of time for specified quality to become available, '
                                    'after that fall back to best so far')
    add_subparser.add_argument('--upgrade', type=bool,
                               help='Keeps getting the better qualities as they become available.')
    add_subparser.add_argument('--target', type=SeriesListType.quality_req_type,
                               help='The target quality that should be downloaded without waiting for `timeframe` '
                                    'to complete')
    add_subparser.add_argument('--specials', type=bool, help='Turn off specials support for series. On by default',
                               default=True)
    add_subparser.add_argument('--no-propers', dest="propers", action='store_false',
                               help='Turn off propers for the series')
    add_subparser.add_argument('--allow-propers', dest="propers", action='store_true',
                               help='Turn on propers for the series')
    add_subparser.add_argument('--propers-interval', dest="propers", type=SeriesListType.interval_type,
                               help='Set propers interval.')
    add_subparser.add_argument('--identified-by', choices=('ep', 'date', 'sequence', 'id', 'auto'),
                               help='Configure how episode numbering is detected. Uses `auto` mode as default',
                               default='auto')
    add_subparser.add_argument('--exact', type=bool, help='Enable strict name matching')
    add_subparser.add_argument('--begin-ep', type=SeriesListType.episode_identifier, dest="begin",
                               help='Manually specify first episode to start series on. Should conform to '
                                    '`SxxEyy` format')
    add_subparser.add_argument('--begin-date', type=SeriesListType.date_identifier, dest="begin",
                               help='Manually specify first episode to start series on. Should conform to '
                                    '`YYYY-MM-DD` format')
    add_subparser.add_argument('--begin-sequence', type=SeriesListType.sequence_identifier, dest="begin",
                               help='Manually specify first episode to start series on. Should be higher an'
                                    ' integer than 0')
    add_subparser.add_argument('--from-group', nargs='+', help='Accept series only from given groups')
    add_subparser.add_argument('--parse-only', type=bool,
                               help='Series plugin will not accept or reject any entries, merely fill in all'
                                    ' metadata fields.')
    add_subparser.add_argument('--special-ids', nargs='+',
                               help='Defines other IDs which will cause entries to be flagged as specials')
    add_subparser.add_argument('--prefer-specials', type=bool,
                               help='Flag entries matching both special and a normal ID type as specials')
    add_subparser.add_argument('--assume-special', type=bool,
                               help='Assume any entry with no series numbering detected is a special and treat it'
                                    ' accordingly')
    add_subparser.add_argument('--no-tracking', dest="tracking", action='store_false',
                               help='Turn off tracking for the series')
    add_subparser.add_argument('--allow-tracking', dest="tracking", action='store_true',
                               help='Turn on tracking for the series')
    add_subparser.add_argument('--tracking', choices=('backfill',), help='Put into backfill mode')
    add_subparser.add_argument('-i', '--identifiers', metavar='<identifiers>', nargs='+',
                               type=SeriesListType.series_list_keyword_type,
                               help='Can be a string or a list of string with the format tvdb_id=XXX,'
                                    ' trakt_show_id=XXX, etc')
