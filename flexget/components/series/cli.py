import argparse
import os
from datetime import timedelta

import flexget.components.series.utils
from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, colorize, console, table_parser

from . import db

# Environment variables to set defaults for `series list` and `series show`
ENV_SHOW_SORTBY_FIELD = 'FLEXGET_SERIES_SHOW_SORTBY_FIELD'
ENV_SHOW_SORTBY_ORDER = 'FLEXGET_SERIES_SHOW_SORTBY_ORDER'
ENV_LIST_CONFIGURED = 'FLEXGET_SERIES_LIST_CONFIGURED'
ENV_LIST_PREMIERES = 'FLEXGET_SERIES_LIST_PREMIERES'
ENV_LIST_SORTBY_FIELD = 'FLEXGET_SERIES_LIST_SORTBY_FIELD'
ENV_LIST_SORTBY_ORDER = 'FLEXGET_SERIES_LIST_SORTBY_ORDER'
ENV_ADD_QUALITY = 'FLEXGET_SERIES_ADD_QUALITY'
# Colors for console output
SORT_COLUMN_COLOR = 'yellow'
NEW_EP_COLOR = 'green'
FRESH_EP_COLOR = 'yellow'
OLD_EP_COLOR = 'default'
BEHIND_EP_COLOR = 'red'
UNDOWNLOADED_RELEASE_COLOR = 'default'
DOWNLOADED_RELEASE_COLOR = 'green'
ERROR_COLOR = 'red'


def do_cli(manager, options):
    if hasattr(options, 'table_type') and options.table_type == 'porcelain':
        flexget.terminal.disable_colors()
    if options.series_action == 'list':
        display_summary(options)
    elif options.series_action == 'show':
        display_details(options)
    elif options.series_action == 'remove':
        remove(manager, options)
    elif options.series_action == 'forget':
        remove(manager, options, forget=True)
    elif options.series_action == 'begin':
        begin(manager, options)
    elif options.series_action == 'add':
        add(manager, options)


def display_summary(options):
    """
    Display series summary.
    :param options: argparse options from the CLI
    """
    porcelain = options.table_type == 'porcelain'
    configured = options.configured or os.environ.get(ENV_LIST_CONFIGURED, 'configured')
    premieres = (
        True if (os.environ.get(ENV_LIST_PREMIERES) == 'yes' or options.premieres) else False
    )
    sort_by = options.sort_by or os.environ.get(ENV_LIST_SORTBY_FIELD, 'name')
    if options.order is not None:
        descending = True if options.order == 'desc' else False
    else:
        descending = True if os.environ.get(ENV_LIST_SORTBY_ORDER) == 'desc' else False
    with Session() as session:
        kwargs = {
            'configured': configured,
            'premieres': premieres,
            'session': session,
            'sort_by': sort_by,
            'descending': descending,
        }
        if sort_by == 'name':
            kwargs['sort_by'] = 'show_name'
        else:
            kwargs['sort_by'] = 'last_download_date'

        query = db.get_series_summary(**kwargs)
        header = ['Name', 'Begin', 'Last Encountered', 'Age', 'Downloaded', 'Identified By']
        for index, value in enumerate(header):
            if value.lower() == options.sort_by:
                header[index] = colorize(SORT_COLUMN_COLOR, value)
        table = TerminalTable(*header, table_type=options.table_type)

        for series in query:
            name_column = series.name

            behind = (0,)
            begin = series.begin.identifier if series.begin else '-'
            latest_release = '-'
            age_col = '-'
            episode_id = '-'
            latest = db.get_latest_release(series)
            identifier_type = series.identified_by
            if identifier_type == 'auto':
                identifier_type = colorize('yellow', 'auto')
            if latest:
                behind = db.new_entities_after(latest)
                latest_release = get_latest_status(latest)
                # colorize age
                age_col = latest.age
                if latest.age_timedelta is not None:
                    if latest.age_timedelta < timedelta(days=1):
                        age_col = colorize(NEW_EP_COLOR, latest.age)
                    elif latest.age_timedelta < timedelta(days=3):
                        age_col = colorize(FRESH_EP_COLOR, latest.age)
                    elif latest.age_timedelta > timedelta(days=400):
                        age_col = colorize(OLD_EP_COLOR, latest.age)
                episode_id = latest.identifier
            if not porcelain:
                if behind[0] > 0:
                    name_column += colorize(BEHIND_EP_COLOR, f' {behind[0]} {behind[1]} behind')

            table.add_row(name_column, begin, episode_id, age_col, latest_release, identifier_type)
    console(table)
    if not porcelain:
        if not query.count():
            console('Use `flexget series list all` to view all known series.')
        else:
            console('Use `flexget series show NAME` to get detailed information.')


def begin(manager, options):
    series_name = options.series_name
    series_name = series_name.replace(r'\!', '!')
    normalized_name = flexget.components.series.utils.normalize_series_name(series_name)
    with Session() as session:
        series = db.shows_by_exact_name(normalized_name, session)
        if options.forget:
            if not series:
                console('Series `%s` was not found in the database.' % series_name)
            else:
                series = series[0]
                series.begin = None
                console('The begin episode for `%s` has been forgotten.' % series.name)
                session.commit()
                manager.config_changed()
        elif options.episode_id:
            ep_id = options.episode_id
            if not series:
                console('Series not yet in database. Adding `%s`.' % series_name)
                series = db.Series()
                series.name = series_name
                session.add(series)
            else:
                series = series[0]
            try:
                _, entity_type = db.set_series_begin(series, ep_id)
            except ValueError as e:
                console(e)
            else:
                if entity_type == 'season':
                    console('`%s` was identified as a season.' % ep_id)
                    ep_id += 'E01'
                console(f'Releases for `{series.name}` will be accepted starting with `{ep_id}`.')
                session.commit()
            manager.config_changed()


def remove(manager, options, forget=False):
    name = options.series_name
    if options.episode_id:
        for identifier in options.episode_id:
            try:
                db.remove_series_entity(name, identifier, forget)
            except ValueError as e:
                console(e.args[0])
            else:
                console(
                    f'Removed entities(s) matching `{identifier}` from series `{name.capitalize()}`.'
                )
    else:
        # remove whole series
        try:
            db.remove_series(name, forget)
        except ValueError as e:
            console(e.args[0])
        else:
            console('Removed series `%s` from database.' % name.capitalize())

    manager.config_changed()


def get_latest_status(episode):
    """
    :param episode: Instance of Episode
    :return: Status string for given episode
    """
    status = ''
    for release in sorted(episode.releases, key=lambda r: r.quality):
        if not release.downloaded:
            continue
        status += release.quality.name
        if release.proper_count > 0:
            status += '-proper'
            if release.proper_count > 1:
                status += str(release.proper_count)
        status += ', '
    return status.rstrip(', ') if status else None


def display_details(options):
    """Display detailed series information, ie. series show NAME"""
    name = options.series_name
    sort_by = options.sort_by or os.environ.get(ENV_SHOW_SORTBY_FIELD, 'age')
    if options.order is not None:
        reverse = True if options.order == 'desc' else False
    else:
        reverse = True if os.environ.get(ENV_SHOW_SORTBY_ORDER) == 'desc' else False
    with Session() as session:
        name = flexget.components.series.utils.normalize_series_name(name)
        # Sort by length of name, so that partial matches always show shortest matching title
        matches = db.shows_by_name(name, session=session)
        if not matches:
            console(colorize(ERROR_COLOR, 'ERROR: Unknown series `%s`' % name))
            return
        # Pick the best matching series
        series = matches[0]
        table_title = series.name
        if len(matches) > 1:
            warning = (
                colorize('red', ' WARNING: ') + 'Multiple series match to `{}`.\n '
                'Be more specific to see the results of other matches:\n\n'
                ' {}'.format(name, ', '.join(s.name for s in matches[1:]))
            )
            if not options.table_type == 'porcelain':
                console(warning)
        header = ['Identifier', 'Last seen', 'Release titles', 'Quality', 'Proper']
        table_data = []
        entities = db.get_all_entities(series, session=session, sort_by=sort_by, reverse=reverse)
        for entity in entities:
            if not entity.releases:
                continue
            if entity.identifier is None:
                identifier = colorize(ERROR_COLOR, 'MISSING')
                age = ''
            else:
                identifier = entity.identifier
                age = entity.age
            entity_data = [identifier, age]
            release_titles = []
            release_qualities = []
            release_propers = []
            for release in entity.releases:
                title = release.title
                quality = release.quality.name
                if not release.downloaded:
                    title = colorize(UNDOWNLOADED_RELEASE_COLOR, title)
                    quality = quality
                else:
                    title += ' *'
                    title = colorize(DOWNLOADED_RELEASE_COLOR, title)
                    quality = quality
                release_titles.append(title)
                release_qualities.append(quality)
                release_propers.append('Yes' if release.proper_count > 0 else '')
            entity_data.append('\n'.join(release_titles))
            entity_data.append('\n'.join(release_qualities))
            entity_data.append('\n'.join(release_propers))
            table_data.append(entity_data)
        footer = ' %s \n' % (colorize(DOWNLOADED_RELEASE_COLOR, '* Downloaded'))
        if not series.identified_by:
            footer += (
                '\n Series plugin is still learning which episode numbering mode is \n'
                ' correct for this series (identified_by: auto).\n'
                ' Few duplicate downloads can happen with different numbering schemes\n'
                ' during this time.'
            )
        else:
            footer += '\n `{}` uses `{}` mode to identify episode numbering.'.format(
                series.name,
                series.identified_by,
            )
        begin_text = 'option'
        if series.begin:
            footer += f' \n Begin for `{series.name}` is set to `{series.begin.identifier}`.'
            begin_text = 'and `begin` options'
        footer += ' \n See `identified_by` %s for more information.' % begin_text
    table = TerminalTable(*header, table_type=options.table_type, title=table_title)
    for row in table_data:
        table.add_row(*row)
    console(table)
    if not options.table_type == 'porcelain':
        console(footer)


def add(manager, options):
    series_name = options.series_name
    entity_ids = options.entity_id
    quality = options.quality or os.environ.get(ENV_ADD_QUALITY, None)
    series_name = series_name.replace(r'\!', '!')
    normalized_name = flexget.components.series.utils.normalize_series_name(series_name)
    with Session() as session:
        series = db.shows_by_exact_name(normalized_name, session)
        if not series:
            console('Series not yet in database, adding `%s`' % series_name)
            series = db.Series()
            series.name = series_name
            session.add(series)
        else:
            series = series[0]
        for ent_id in entity_ids:
            try:
                db.add_series_entity(session, series, ent_id, quality=quality)
            except ValueError as e:
                console(e.args[0])
            else:
                console(f'Added entity `{ent_id}` to series `{series.name.title()}`.')
        session.commit()
    manager.config_changed()


@event('options.register')
def register_parser_arguments():
    # Register the command
    parser = options.register_command(
        'series', do_cli, help='View and manipulate the series plugin database'
    )

    # Parent parser for subcommands that need a series name
    series_parser = argparse.ArgumentParser(add_help=False)
    series_parser.add_argument(
        'series_name', help='The name of the series', metavar='<series name>'
    )

    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='series_action')
    list_parser = subparsers.add_parser(
        'list', parents=[table_parser], help='List a summary of the different series being tracked'
    )
    list_parser.add_argument(
        'configured',
        nargs='?',
        choices=['configured', 'unconfigured', 'all'],
        help='Limit list to series that are currently in the config or not (default: %(default)s)',
    )
    list_parser.add_argument(
        '--premieres',
        action='store_true',
        help='limit list to series which only have episode 1 (and maybe also 2) downloaded',
    )
    list_parser.add_argument(
        '--sort-by', choices=('name', 'age'), help='Choose list sort attribute'
    )
    order = list_parser.add_mutually_exclusive_group(required=False)
    order.add_argument(
        '--descending',
        dest='order',
        action='store_const',
        const='desc',
        help='Sort in descending order',
    )
    order.add_argument(
        '--ascending',
        dest='order',
        action='store_const',
        const='asc',
        help='Sort in ascending order',
    )

    show_parser = subparsers.add_parser(
        'show',
        parents=[series_parser, table_parser],
        help='Show the releases FlexGet has seen for a given series',
    )
    show_parser.add_argument(
        '--sort-by',
        choices=('age', 'identifier'),
        help='Choose releases list sort: age (default) or identifier',
    )
    show_order = show_parser.add_mutually_exclusive_group(required=False)
    show_order.add_argument(
        '--descending',
        dest='order',
        action='store_const',
        const='desc',
        help='Sort in descending order',
    )
    show_order.add_argument(
        '--ascending',
        dest='order',
        action='store_const',
        const='asc',
        help='Sort in ascending order',
    )

    begin_parser = subparsers.add_parser(
        'begin', parents=[series_parser], help='set the episode to start getting a series from'
    )
    begin_opts = begin_parser.add_mutually_exclusive_group(required=True)
    begin_opts.add_argument(
        '--forget', dest='forget', action='store_true', help='Forget begin episode', required=False
    )
    begin_opts.add_argument(
        'episode_id',
        metavar='<episode ID>',
        help='Episode ID to start getting the series from (e.g. S02E01, 2013-12-11, or 9, '
        'depending on how the series is numbered). You can also enter a season ID such as '
        ' S02.',
        nargs='?',
        default='',
    )

    addshow_parser = subparsers.add_parser(
        'add', parents=[series_parser], help='Add episode(s) and season(s) to series history'
    )
    addshow_parser.add_argument(
        'entity_id',
        nargs='+',
        default=None,
        metavar='<entity_id>',
        help='Episode or season entity ID(s) to add',
    )
    addshow_parser.add_argument(
        '--quality',
        default=None,
        metavar='<quality>',
        help='Quality string to be stored for all entity ID(s)',
    )

    forget_parser = subparsers.add_parser(
        'forget',
        parents=[series_parser],
        help='Removes episodes or whole series from the entire database '
        '(including seen plugin)',
    )
    forget_parser.add_argument(
        'episode_id', nargs='*', default=None, help='Entity ID(s) to forget (optional)'
    )
    delete_parser = subparsers.add_parser(
        'remove',
        parents=[series_parser],
        help='Removes episodes or whole series from the series database only',
    )
    delete_parser.add_argument(
        'episode_id', nargs='*', default=None, help='Episode ID to forget (optional)'
    )
