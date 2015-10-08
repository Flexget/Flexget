from __future__ import unicode_literals, division, absolute_import
import argparse
from datetime import datetime, timedelta
from sqlalchemy import func

from flexget import options, plugin
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session

try:
    from flexget.plugins.filter.series import (Series, Episode, Release, SeriesTask, forget_series,
                                               forget_series_episode, set_series_begin, normalize_series_name,
                                               new_eps_after, get_latest_release)
except ImportError:
    raise plugin.DependencyError(issued_by='cli_series', missing='series',
                                 message='Series commandline interface not loaded')


def do_cli(manager, options):
    if options.series_action == 'list':
        display_summary(options)
    elif options.series_action == 'show':
        display_details(options.series_name)
    elif options.series_action == 'forget':
        forget(manager, options)
    elif options.series_action == 'begin':
        begin(manager, options)


def display_summary(options):
    """
    Display series summary.
    :param options: argparse options from the CLI
    """
    session = Session()
    try:
        query = (session.query(Series).outerjoin(Series.episodes).outerjoin(Episode.releases).
                 outerjoin(Series.in_tasks).group_by(Series.id))
        if options.configured == 'configured':
            query = query.having(func.count(SeriesTask.id) >= 1)
        elif options.configured == 'unconfigured':
            query = query.having(func.count(SeriesTask.id) < 1)
        if options.premieres:
            query = (query.having(func.max(Episode.season) <= 1).having(func.max(Episode.number) <= 2).
                     having(func.count(SeriesTask.id) < 1)).filter(Release.downloaded == True)
        if options.new:
            query = query.having(func.max(Episode.first_seen) > datetime.now() - timedelta(days=options.new))
        if options.stale:
            query = query.having(func.max(Episode.first_seen) < datetime.now() - timedelta(days=options.stale))
        if options.porcelain:
            formatting = '%-30s %s %-10s %s %-10s %s %-20s'
            console(formatting % ('Name', '|', 'Latest', '|', 'Age', '|', 'Downloaded'))
        else:
            formatting = ' %-30s %-10s %-10s %-20s'
            console('-' * 79)
            console(formatting % ('Name', 'Latest', 'Age', 'Downloaded'))
            console('-' * 79)
        for series in query.order_by(Series.name).yield_per(10):
            series_name = series.name
            if len(series_name) > 30:
                series_name = series_name[:27] + '...'

            new_ep = ' '
            behind = 0
            status = 'N/A'
            age = 'N/A'
            episode_id = 'N/A'
            latest = get_latest_release(series)
            if latest:
                if latest.first_seen > datetime.now() - timedelta(days=2):
                    if options.porcelain:
                        pass
                    else:
                        new_ep = '>'
                behind = new_eps_after(latest)
                status = get_latest_status(latest)
                age = latest.age
                episode_id = latest.identifier

            if behind:
                episode_id += ' +%s' % behind

            if options.porcelain:
                console(formatting % (series_name, '|', episode_id, '|', age, '|', status))
            else:
                console(new_ep + formatting[1:] % (series_name, episode_id, age, status))
            if behind >= 3:
                console(' ! Latest download is %d episodes behind, this may require '
                        'manual intervention' % behind)

        if options.porcelain:
            pass
        else:
            console('-' * 79)
            console(' > = new episode ')
            console(' Use `flexget series show NAME` to get detailed information')
    finally:
        session.close()


def begin(manager, options):
    series_name = options.series_name
    ep_id = options.episode_id
    session = Session()
    try:
        series = session.query(Series).filter(Series.name == series_name).first()
        if not series:
            console('Series not yet in database, adding `%s`' % series_name)
            series = Series()
            series.name = series_name
            session.add(series)
        try:
            set_series_begin(series, ep_id)
        except ValueError as e:
            console(e)
        else:
            console('Episodes for `%s` will be accepted starting with `%s`' % (series.name, ep_id))
            session.commit()
    finally:
        session.close()
    manager.config_changed()


def forget(manager, options):
    name = options.series_name

    if options.episode_id:
        # remove by id
        identifier = options.episode_id
        try:
            forget_series_episode(name, identifier)
            console('Removed episode `%s` from series `%s`.' % (identifier, name.capitalize()))
        except ValueError:
            # Try upper casing identifier if we fail at first
            try:
                forget_series_episode(name, identifier.upper())
                console('Removed episode `%s` from series `%s`.' % (identifier, name.capitalize()))
            except ValueError as e:
                console(e.message)
    else:
        # remove whole series
        try:
            forget_series(name)
            console('Removed series `%s` from database.' % name.capitalize())
        except ValueError as e:
            console(e.message)

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


def display_details(name):
    """Display detailed series information, ie. series show NAME"""

    from flexget.manager import Session
    with Session() as session:

        name = normalize_series_name(name)
        # Sort by length of name, so that partial matches always show shortest matching title
        matches = (session.query(Series).filter(Series._name_normalized.contains(name)).
                   order_by(func.char_length(Series.name)).all())
        if not matches:
            console('ERROR: Unknown series `%s`' % name)
            return
        # Pick the best matching series
        series = matches[0]
        console('Showing results for `%s`.' % series.name)
        if len(matches) > 1:
            console('WARNING: Multiple series match to `%s`.' % name)
            console('Be more specific to see the results of other matches:')
            for s in matches[1:]:
                console(' - %s' % s.name)

        console(' %-63s%-15s' % ('Identifier, Title', 'Quality'))
        console('-' * 79)

        # Query episodes in sane order instead of iterating from series.episodes
        episodes = session.query(Episode).filter(Episode.series_id == series.id)
        if series.identified_by == 'sequence':
            episodes = episodes.order_by(Episode.number).all()
        elif series.identified_by == 'ep':
            episodes = episodes.order_by(Episode.season, Episode.number).all()
        else:
            episodes = episodes.order_by(Episode.identifier).all()

        for episode in episodes:

            if episode.identifier is None:
                console(' None <--- Broken!')
            else:
                console(' %s (%s) - %s' % (episode.identifier, episode.identified_by or 'N/A', episode.age))

            for release in episode.releases:
                status = release.quality.name
                title = release.title
                if len(title) > 55:
                    title = title[:55] + '...'
                if release.proper_count > 0:
                    status += '-proper'
                    if release.proper_count > 1:
                        status += str(release.proper_count)
                if release.downloaded:
                    console('  * %-60s%-15s' % (title, status))
                else:
                    console('    %-60s%-15s' % (title, status))

        console('-' * 79)
        console(' * = downloaded')
        if not series.identified_by:
            console('')
            console(' Series plugin is still learning which episode numbering mode is ')
            console(' correct for this series (identified_by: auto).')
            console(' Few duplicate downloads can happen with different numbering schemes')
            console(' during this time.')
        else:
            console(' Series uses `%s` mode to identify episode numbering (identified_by).' % series.identified_by)
        console(' See option `identified_by` for more information.')
        if series.begin:
            console(' Begin episode for this series set to `%s`.' % series.begin.identifier)


@event('options.register')
def register_parser_arguments():
    # Register the command
    parser = options.register_command('series', do_cli, help='view and manipulate the series plugin database')

    # Parent parser for subcommands that need a series name
    series_parser = argparse.ArgumentParser(add_help=False)
    series_parser.add_argument('series_name', help='the name of the series', metavar='<series name>')

    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='series_action')
    list_parser = subparsers.add_parser('list', help='list a summary of the different series being tracked')
    list_parser.add_argument('configured', nargs='?', choices=['configured', 'unconfigured', 'all'],
                             default='configured',
                             help='limit list to series that are currently in the config or not (default: %(default)s)')
    list_parser.add_argument('--premieres', action='store_true',
                             help='limit list to series which only have episode 1 (and maybe also 2) downloaded')
    list_parser.add_argument('--new', nargs='?', type=int, metavar='DAYS', const=7,
                             help='limit list to series with a release seen in last %(const)s days. number of days can '
                                  'be overridden with %(metavar)s')
    list_parser.add_argument('--stale', nargs='?', type=int, metavar='DAYS', const=365,
                             help='limit list to series which have not seen a release in %(const)s days. number of '
                                  'days can be overridden with %(metavar)s')
    list_parser.add_argument('--porcelain', action='store_true', help='make the output parseable')
    show_parser = subparsers.add_parser('show', parents=[series_parser],
                                        help='show the releases FlexGet has seen for a given series ')
    begin_parser = subparsers.add_parser('begin', parents=[series_parser],
                                         help='set the episode to start getting a series from')
    begin_parser.add_argument('episode_id', metavar='<episode ID>',
                              help='episode ID to start getting the series from (e.g. S02E01, 2013-12-11, or 9, '
                                   'depending on how the series is numbered)')
    forget_parser = subparsers.add_parser('forget', parents=[series_parser],
                                          help='removes episodes or whole series from the series database')
    forget_parser.add_argument('episode_id', nargs='?', default=None, help='episode ID to forget (optional)')
