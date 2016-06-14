from __future__ import unicode_literals, division, absolute_import

import re
from argparse import ArgumentParser, ArgumentTypeError

from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.utils import qualities
from flexget.config_schema import parse_interval
from flexget.plugins.list.series_list import SeriesListList, SeriesListDB as slDb, SeriesList
from flexget.plugins.filter.series import FilterSeriesBase

SERIES_ATTRIBUTES = FilterSeriesBase().settings_schema['properties']


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
            raise ArgumentTypeError('Received identifier in wrong format: {}, '
                                    'should be in keyword format like `tvdb_id=1234567`'.format(identifier))
        name, value = identifier.split('=', 2)
        if name not in FilterSeriesBase().supported_ids():
            raise ArgumentTypeError(
                'Received unsupported identifier ID {}. Should be one of {}'.format(identifier,
                                                                                    ' ,'.join(
                                                                                        FilterSeriesBase().supported_ids())))
        return {name: value}

    @staticmethod
    def keyword_type(identifier):
        if identifier.count('=') != 1:
            raise ArgumentTypeError('Received identifier in wrong format: {}, '
                                    'should be in keyword format like `movedone=/a/random/path`'.format(identifier))
        name, value = identifier.split('=', 2)
        return {name: value}

    @staticmethod
    def exiting_attribute(value):
        if value not in SERIES_ATTRIBUTES:
            raise ArgumentTypeError('Value {} is not a valid series attribute'.format(value))
        return value

    @staticmethod
    def tracking_attribute(value):
        attributes_list = tracking_attributes(SERIES_ATTRIBUTES)
        if value not in attributes_list:
            raise ArgumentTypeError(
                'Value {} cannot be used when updating an entire list, only tracking related attributes'
                ' are relevant'.format(value))
        return value


def tracking_attributes(attributes_list):
    del attributes_list['alternate_name']
    del attributes_list['name_regexp']
    del attributes_list['ep_regexp']
    del attributes_list['date_regexp']
    del attributes_list['sequence_regexp']
    del attributes_list['id_regexp']
    del attributes_list['date_yearfirst']
    del attributes_list['date_dayfirst']
    del attributes_list['identified_by']
    return attributes_list


def build_data_dict(options, tracking_only=False):
    """ Converts options to a recognizable data type for series adding/matching"""
    attributes_list = SERIES_ATTRIBUTES
    data = {}
    if not tracking_only:
        data['series_name'] = options.series_title
        if options.identifiers:
            for identifier in options.identifiers:
                if identifier in FilterSeriesBase().supported_ids():
                    for k, v in identifier.items():
                        data[k] = v
    else:
        attributes_list = tracking_attributes(attributes_list)
    for attribute in attributes_list:
        data[attribute] = getattr(options, attribute)
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

    if options.list_action == 'show':
        series_list_show(options)
        return

    if options.list_action == 'update-series':
        series_list_update_series(options)
        return

    if options.list_action == 'update-list':
        series_list_update_list(options)
        return

    if options.list_action == 'delete':
        series_list_del(options)
        return

    if options.list_action == 'purge':
        series_list_purge(options)
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
            title_string = '{:2d}: {} '.format(series.id, series.title)
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
        session.commit()
        data = build_data_dict(options)
        series = SeriesList(options.list_name, session=session).find_entry(data, session=session)
        if series:
            console('Series with title {} already exist'.format(options.series_title))
            return
        series = slDb.get_db_series(data)
        series.list_id = series_list.id
        session.add(series)
        console('Successfully added series {} to list {}'.format(series.title, series_list.name))


def series_list_show(options):
    """ Shows a series in list with detail """
    with Session() as session:
        try:
            series_list = slDb.get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find series list with name {}'.format(options.list_name))
            return

        try:
            series = slDb.get_series_by_id(series_list.id, int(options.series_title), session=session)
        except NoResultFound:
            console(
                'Could not find matching series with ID {} in list `{}`'.format(int(options.series_title),
                                                                                options.list_name))
            return
        except ValueError:
            series = slDb.get_series_by_title(series_list.id, options.series_title, session=session)
            if not series:
                console(
                    'Could not find matching series with title `{}` in list `{}`'.format(options.series,
                                                                                         options.list_name))
                return
        console('Showing fields for series #{}: {}'.format(series.id, series.title))
        console('-' * 79)
        for attribute in SERIES_ATTRIBUTES:
            console('{}: {}'.format(attribute.capitalize(), series.format_converter(attribute)))


def series_list_update_series(options):
    with Session() as session:
        try:
            series_list = slDb.get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find series list with name {}'.format(options.list_name))
            return

        try:
            series = slDb.get_series_by_id(series_list.id, int(options.series_title), session=session)
        except NoResultFound:
            console(
                'Could not find matching series with ID {} in list `{}`'.format(int(options.series_title),
                                                                                options.list_name))
            return
        except ValueError:
            series = slDb.get_series_by_title(series_list.id, options.series_title, session=session)
            if not series:
                console(
                    'Could not find matching series with title `{}` in list `{}`'.format(options.series_title,
                                                                                         options.list_name))

        console('Updating series #{}: {}'.format(series.id, series.title))
        if options.clear:
            for attribute in options.clear:
                console('Resetting attribute {}'.format(attribute))
                setattr(series, attribute, None)
            return
        data = build_data_dict(options)
        series = slDb.get_db_series(data, series)
        session.commit()
        console('Successfully updated series #{}: {}'.format(series.id, series.title))


def series_list_update_list(options):
    with Session() as session:
        try:
            series_list = slDb.get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find series list with name {}'.format(options.list_name))
            return
        console('Updating all series in list {} with given options'.format(series_list.name))
        updated_series_list = []
        data = build_data_dict(options, tracking_only=True)
        for series in slDb.get_series_by_list_id(series_list.id, descending=True, session=session):
            if options.clear:
                for attribute in options.clear:
                    setattr(series, attribute, None)
            updated_series_list.append(slDb.get_db_series(data, series))
        series_list.series = updated_series_list
        session.commit()
        console('Successfully updated {} series'.format(len(updated_series_list)))


def series_list_del(options):
    with Session() as session:
        try:
            series_list = slDb.get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find series list with name {}'.format(options.list_name))
            return

        try:
            series = slDb.get_series_by_id(series_list.id, int(options.series_title), session=session)
        except NoResultFound:
            console(
                'Could not find matching series with ID {} in list `{}`'.format(int(options.series_title),
                                                                                options.list_name))
            return
        except ValueError:
            series = slDb.get_series_by_title(series_list.id, options.series_title, session=session)
            if not series:
                console(
                    'Could not find matching series with title `{}` in list `{}`'.format(options.series_title,
                                                                                         options.list_name))
        session.delete(series)
        console('Successfully deleted series {} from series list {}'.format(options.series_title, options.list_name))


def series_list_purge(options):
    with Session() as session:
        try:
            series_list = slDb.get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find series list with name {}'.format(options.list_name))
            return
        console('Deleting list {}'.format(options.list_name))
        session.delete(series_list)


@event('options.register')
def register_parser_arguments():
    series_parser = ArgumentParser(add_help=False)
    series_parser.add_argument('series_title', metavar='series-title',
                               help="Title of the series. Should include country code if relevant")

    # This parser will be used when series ID can be used
    series_id_parser = ArgumentParser(add_help=False)
    series_id_parser.add_argument('series_title', metavar='series-title', help="Series title or ID")

    list_name_parser = ArgumentParser(add_help=False)
    list_name_parser.add_argument('list_name', nargs='?', default='series',
                                  help='Name of series list to operate on. Default is `series`')

    series_attributes_identity_parser = ArgumentParser(add_help=False)
    series_attributes_identity_parser.add_argument('--set', type=SeriesListType.keyword_type, nargs='+',
                                                   help='Use set plugin to set any fields for this series')

    series_attributes_identity_parser.add_argument('--path', help='Set path field for this series')
    series_attributes_identity_parser.add_argument('-a', '--alternate-name', nargs='+', help='Alternate series name(s)')
    series_attributes_identity_parser.add_argument('--name-regexp', nargs='+', type=SeriesListType.regex_type,
                                                   help='Manually specify regexp(s) that matches to series name')
    series_attributes_identity_parser.add_argument('--ep-regexp', nargs='+', type=SeriesListType.regex_type,
                                                   help='Manually specify regexp(s) that matches to episode, season numbering')
    series_attributes_identity_parser.add_argument('--date-regexp', nargs='+', type=SeriesListType.regex_type,
                                                   help='Date regexp')
    series_attributes_identity_parser.add_argument('--sequence-regexp', nargs='+', type=SeriesListType.regex_type,
                                                   help='Sequence regexp')
    series_attributes_identity_parser.add_argument('--id-regexp', nargs='+', type=SeriesListType.regex_type,
                                                   help='Manually specify regexp(s) that matches to series identifier '
                                                        '(numbering)')
    series_attributes_identity_parser.add_argument('--date-yearfirst', type=bool, help='Parse year first')
    series_attributes_identity_parser.add_argument('--date-dayfirst', type=bool, help='Parse date first')
    series_attributes_identity_parser.add_argument('--identified-by', choices=('ep', 'date', 'sequence', 'id', 'auto'),
                                                   help='Configure how episode numbering is detected. Uses `auto` mode as '
                                                        'default', default='auto')
    series_attributes_identity_parser.add_argument('-i', '--identifiers', metavar='<identifiers>', nargs='+',
                                                   type=SeriesListType.series_list_keyword_type,
                                                   help='Can be a string or a list of string with the format tvdb_id=XXX,'
                                                        ' trakt_show_id=XXX, etc')

    series_attributes_tracking_parser = ArgumentParser(add_help=False)
    series_attributes_tracking_parser.add_argument('-q', '--quality', type=SeriesListType.quality_req_type,
                                                   help='Required quality')
    series_attributes_tracking_parser.add_argument('--qualities', type=SeriesListType.quality_req_type, nargs='+',
                                                   help='Download all listed qualities when they become available')
    series_attributes_tracking_parser.add_argument('--timeframe', type=SeriesListType.interval_type,
                                                   help='Wait given amount of time for specified quality to become available, '
                                                        'after that fall back to best so far')
    series_attributes_tracking_parser.add_argument('--upgrade', type=bool,
                                                   help='Keeps getting the better qualities as they become available.')
    series_attributes_tracking_parser.add_argument('--target', type=SeriesListType.quality_req_type,
                                                   help='The target quality that should be downloaded without waiting'
                                                        ' for `timeframe` to complete')
    series_attributes_tracking_parser.add_argument('--specials', type=bool,
                                                   help='Turn off specials support for series. On by default',
                                                   default=True)
    series_attributes_tracking_parser.add_argument('--no-propers', dest="propers", action='store_false',
                                                   help='Turn off propers for the series')
    series_attributes_tracking_parser.add_argument('--allow-propers', dest="propers", action='store_true',
                                                   help='Turn on propers for the series')
    series_attributes_tracking_parser.add_argument('--propers-interval', dest="propers",
                                                   type=SeriesListType.interval_type,
                                                   help='Set propers interval.')

    series_attributes_tracking_parser.add_argument('--exact', type=bool, help='Enable strict name matching')
    series_attributes_tracking_parser.add_argument('--begin-ep', type=SeriesListType.episode_identifier, dest="begin",
                                                   help='Manually specify first episode to start series on. Should conform to '
                                                        '`SxxEyy` format')
    series_attributes_tracking_parser.add_argument('--begin-date', type=SeriesListType.date_identifier, dest="begin",
                                                   help='Manually specify first episode to start series on. Should conform to '
                                                        '`YYYY-MM-DD` format')
    series_attributes_tracking_parser.add_argument('--begin-sequence', type=SeriesListType.sequence_identifier,
                                                   dest="begin",
                                                   help='Manually specify first episode to start series on. Should be higher an'
                                                        ' integer than 0')
    series_attributes_tracking_parser.add_argument('--from-group', nargs='+',
                                                   help='Accept series only from given groups')
    series_attributes_tracking_parser.add_argument('--parse-only', type=bool,
                                                   help='Series plugin will not accept or reject any entries, merely fill in all'
                                                        ' metadata fields.')
    series_attributes_tracking_parser.add_argument('--special-ids', nargs='+',
                                                   help='Defines other IDs which will cause entries to be flagged as specials')
    series_attributes_tracking_parser.add_argument('--prefer-specials', type=bool,
                                                   help='Flag entries matching both special and a normal ID type as specials')
    series_attributes_tracking_parser.add_argument('--assume-special', type=bool,
                                                   help='Assume any entry with no series numbering detected is a special and '
                                                        'treat it accordingly')
    series_attributes_tracking_parser.add_argument('--no-tracking', dest="tracking", action='store_false',
                                                   help='Turn off tracking for the series')
    series_attributes_tracking_parser.add_argument('--allow-tracking', dest="tracking", action='store_true',
                                                   help='Turn on tracking for the series')
    series_attributes_tracking_parser.add_argument('--tracking', choices=('backfill',), help='Put into backfill mode')

    parser = options.register_command('series-list', do_cli, help='View and manage series lists')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='list_action')
    subparsers.add_parser('all', help='Shows all existing series lists')
    subparsers.add_parser('list', parents=[list_name_parser], help='List movies from a list')
    subparsers.add_parser('add', parents=[list_name_parser, series_parser, series_attributes_identity_parser,
                                          series_attributes_tracking_parser],
                          help='Add a series to a list')
    subparsers.add_parser('show', parents=[list_name_parser, series_id_parser], help='Display series attributes')
    update_series_parser = subparsers.add_parser('update-series',
                                                 parents=[list_name_parser, series_id_parser,
                                                          series_attributes_identity_parser,
                                                          series_attributes_tracking_parser],
                                                 help='Update series attributes')
    update_series_parser.add_argument('--clear', nargs='+', type=SeriesListType.exiting_attribute,
                                      help="Clears a series attribute")
    update_list_parser = subparsers.add_parser('update-list',
                                               parents=[list_name_parser, series_attributes_tracking_parser],
                                               help='Update list attributes. This will apply to all series in list. '
                                                    'Note that only series tracking attributes are relevant and not '
                                                    'series identifying attributes such as alternate names.')
    update_list_parser.add_argument('--clear', nargs='+', type=SeriesListType.tracking_attribute,
                                    help="Clears a series attribute from entire series")
    subparsers.add_parser('delete', parents=[list_name_parser, series_id_parser], help='Delete series from series list')
    subparsers.add_parser('purge', parents=[list_name_parser], help='Removes an entire series list. Use with caution.')
