from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import argparse
from datetime import datetime, timedelta
from functools import partial

from flexget import options, plugin
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session

try:
    from flexget.options import CLITable, table_parser, CLITableError
except ImportError:
    raise plugin.DependencyError(issued_by='cli_series', missing='CLITable',
                                 message='Series commandline interface not loaded')

try:
    from flexget.plugins.filter.series import (Series, remove_series, remove_series_episode, set_series_begin,
                                               normalize_series_name, new_eps_after, get_latest_release,
                                               get_series_summary, shows_by_name, show_episodes, shows_by_exact_name)
except ImportError:
    raise plugin.DependencyError(issued_by='cli_series', missing='series',
                                 message='Series commandline interface not loaded')

SORT_COLUMN_COLOR = 'autoyellow'
NEW_EP_COLOR = 'autogreen'
BEHIND_EP_COLOR = 'autored'
DOWNLOADED_RELEASE_COLOR = 'autogreen'
ERROR_COLOR = 'autored'

color = CLITable.colorize
ww = CLITable.word_wrap


def do_cli(manager, options):
    global color
    # Create partial that passes table type, since `porcelain` should disable colors
    if options.series_action in ['list', 'show']:
        color = partial(CLITable.colorize, porcelain=options.table_type == 'porcelain')

    global ww
    ww = partial(CLITable.word_wrap, max_length=options.max_column_width)

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


def display_summary(options):
    """
    Display series summary.
    :param options: argparse options from the CLI
    """
    with Session() as session:
        kwargs = {'configured': options.configured,
                  'premieres': options.premieres,
                  'session': session,
                  'sort_by': options.sort_by,
                  'descending': options.order}
        if options.new:
            kwargs['status'] = 'new'
            kwargs['days'] = options.new
        elif options.stale:
            kwargs['status'] = 'stale'
            kwargs['days'] = options.stale
        if options.sort_by == 'name':
            kwargs['sort_by'] = 'show_name'
        else:
            kwargs['sort_by'] = 'last_download_date'

        query = get_series_summary(**kwargs)
        header = ['Name', 'Latest', 'Age', 'Downloaded', 'Identified By', 'Latest status']
        for index, value in enumerate(header):
            if value.lower() == options.sort_by:
                header[index] = color(value, SORT_COLUMN_COLOR)
        footer = 'Use `flexget series show NAME` to get detailed information'
        table_data = [header]
        for series in query:
            series_name = series.name

            new_ep = False
            behind = 0
            latest_release = '-'
            age = '-'
            episode_id = '-'
            latest = get_latest_release(series)
            status = ''
            identifier_type = series.identified_by
            if latest:
                if latest.first_seen > datetime.now() - timedelta(days=2):
                    new_ep = True
                behind = new_eps_after(latest)
                latest_release = get_latest_status(latest)
                age = latest.age
                episode_id = latest.identifier
            if new_ep:
                status = color('NEW', NEW_EP_COLOR)
            if behind > 0:
                status = color('{} behind'.format(behind), BEHIND_EP_COLOR)
            table_data.append([ww(series_name), episode_id, age, ww(latest_release), identifier_type, status])
    table = CLITable(options.table_type, table_data)
    try:
        console(table.output)
    except CLITableError as e:
        console('ERROR: %s' % str(e))
        return
    if not options.table_type == 'porcelain':
        console(footer)


def begin(manager, options):
    series_name = options.series_name
    ep_id = options.episode_id
    normalized_name = normalize_series_name(series_name)
    with Session() as session:
        series = shows_by_exact_name(normalized_name, session)
        if not series:
            console('Series not yet in database, adding `%s`' % series_name)
            series = Series()
            series.name = series_name
            session.add(series)
        else:
            series = series[0]
        try:
            set_series_begin(series, ep_id)
        except ValueError as e:
            console(e)
        else:
            console('Episodes for `%s` will be accepted starting with `%s`' % (series.name, ep_id))
            session.commit()
        manager.config_changed()


def remove(manager, options, forget=False):
    name = options.series_name
    if options.episode_id:
        # remove by id
        identifier = options.episode_id
        try:
            remove_series_episode(name, identifier, forget)
            console('Removed episode `%s` from series `%s`.' % (identifier, name.capitalize()))
        except ValueError:
            # Try upper casing identifier if we fail at first
            try:
                remove_series_episode(name, identifier.upper(), forget)
                console('Removed episode `%s` from series `%s`.' % (identifier, name.capitalize()))
            except ValueError as e:
                console(e.args[0])

    else:
        # remove whole series
        try:
            remove_series(name, forget)
            console('Removed series `%s` from database.' % name.capitalize())
        except ValueError as e:
            console(e.args[0])

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
    with Session() as session:
        name = normalize_series_name(name)
        # Sort by length of name, so that partial matches always show shortest matching title
        matches = shows_by_name(name, session=session)
        if not matches:
            console(color('ERROR: Unknown series `%s`' % name, ERROR_COLOR))
            return
        # Pick the best matching series
        series = matches[0]
        table_title = 'Showing results for `%s`.' % series.name
        if len(matches) > 1:
            warning = (' WARNING: Multiple series match to `{}`.\n '
                       'Be more specific to see the results of other matches:\n'
                       ' {}'.format(name, '-\n'.join(s.name for s in matches[1:])))
            if not options.table_type == 'porcelain':
                console(warning)
        header = ['Episode ID', 'Latest age', 'Release titles', 'Release Quality', 'Proper']
        table_data = [header]
        episodes = show_episodes(series, session=session, descending=True)
        for episode in episodes:
            if episode.identifier is None:
                identifier = color('MISSING', ERROR_COLOR)
                age = ''
            else:
                identifier = episode.identifier
                age = episode.age
            ep_data = [identifier, age]
            release_titles = []
            release_qualities = []
            release_propers = []
            for release in episode.releases:
                title = release.title
                quality = release.quality.name
                if release.downloaded:
                    title = color(title, DOWNLOADED_RELEASE_COLOR)
                    quality = color(quality, DOWNLOADED_RELEASE_COLOR)
                release_titles.append(ww(title))
                release_qualities.append(ww(quality))
                release_propers.append('Yes' if release.proper_count > 0 else '')
            ep_data.append('\n'.join(release_titles))
            ep_data.append('\n'.join(release_qualities))
            ep_data.append('\n'.join(release_propers))
            table_data.append(ep_data)
        if not series.identified_by:
            footer = ('\n'
                      ' Series plugin is still learning which episode numbering mode is \n'
                      ' correct for this series (identified_by: auto).\n'
                      ' Few duplicate downloads can happen with different numbering schemes\n'
                      ' during this time.')
        else:
            footer = ' Series uses `%s` mode to identify episode numbering (identified_by).\n' % series.identified_by
        footer += ' See option `identified_by` for more information.\n'
        if series.begin:
            footer += ' Begin episode for this series set to `%s`.' % series.begin.identifier
    table = CLITable(options.table_type, table_data, table_title)
    try:
        console(table.output)
    except CLITableError as e:
        console('ERROR: %s' % str(e))
        return
    if not options.table_type == 'porcelain':
        console(footer)


@event('options.register')
def register_parser_arguments():
    # Register the command
    parser = options.register_command('series', do_cli, help='View and manipulate the series plugin database')

    # Parent parser for subcommands that need a series name
    series_parser = argparse.ArgumentParser(add_help=False)
    series_parser.add_argument('series_name', help='The name of the series', metavar='<series name>')

    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='series_action')
    list_parser = subparsers.add_parser('list', parents=[table_parser],
                                        help='List a summary of the different series being tracked')
    list_parser.add_argument('configured', nargs='?', choices=['configured', 'unconfigured', 'all'],
                             default='configured',
                             help='Limit list to series that are currently in the config or not (default: %(default)s)')
    list_parser.add_argument('--premieres', action='store_true',
                             help='limit list to series which only have episode 1 (and maybe also 2) downloaded')
    list_parser.add_argument('--new', nargs='?', type=int, metavar='DAYS', const=7,
                             help='Limit list to series with a release seen in last %(const)s days. number of days can '
                                  'be overridden with %(metavar)s')
    list_parser.add_argument('--stale', nargs='?', type=int, metavar='DAYS', const=365,
                             help='Limit list to series which have not seen a release in %(const)s days. number of '
                                  'days can be overridden with %(metavar)s')
    list_parser.add_argument('--sort-by', choices=('name', 'age'), default='name',
                             help='Choose list sort attribute')
    order = list_parser.add_mutually_exclusive_group(required=False)
    order.add_argument('--descending', dest='order', action='store_true', help='Sort in descending order')
    order.add_argument('--ascending', dest='order', action='store_false', help='Sort in ascending order')

    subparsers.add_parser('show', parents=[series_parser, table_parser],
                          help='Show the releases FlexGet has seen for a given series ')
    begin_parser = subparsers.add_parser('begin', parents=[series_parser],
                                         help='set the episode to start getting a series from')
    begin_parser.add_argument('episode_id', metavar='<episode ID>',
                              help='Episode ID to start getting the series from (e.g. S02E01, 2013-12-11, or 9, '
                                   'depending on how the series is numbered)')
    forget_parser = subparsers.add_parser('forget', parents=[series_parser],
                                          help='Removes episodes or whole series from the entire database '
                                               '(including seen plugin)')
    forget_parser.add_argument('episode_id', nargs='?', default=None, help='episode ID to forget (optional)')
    delete_parser = subparsers.add_parser('remove', parents=[series_parser],
                                          help='Removes episodes or whole series from the series database only')
    delete_parser.add_argument('episode_id', nargs='?', default=None, help='Episode ID to forget (optional)')
