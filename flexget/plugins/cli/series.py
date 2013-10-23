from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta
from string import capwords
from sqlalchemy import func

from flexget.event import event
from flexget.manager import Session
from flexget.plugin import register_plugin, register_parser_option, DependencyError
from flexget.utils.tools import console

try:
    from flexget.plugins.filter.series import (SeriesDatabase, Series, Episode, Release, SeriesTask, forget_series,
                                               forget_series_episode, set_series_begin, normalize_series_name)
except ImportError:
    raise DependencyError(issued_by='cli_series', missing='series', message='Series commandline interface not loaded')


class SeriesReport(SeriesDatabase):
    """Produces --series report"""

    def on_process_start(self, task):
        if task.manager.options.series:
            task.manager.disable_tasks()

            if isinstance(task.manager.options.series, bool):
                self.display_summary()
            else:
                self.display_details(task.manager.options.series)

    def display_details(self, name):
        """Display detailed series information, ie. --series NAME"""

        from flexget.manager import Session
        session = Session()

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
        session.close()

    def get_series_summary(self):
        """
        :return: Dictionary where key is series name and value is dictionary of summary details.
        """
        result = {}
        session = Session()
        try:
            seriestasks = session.query(SeriesTask).all()
            if seriestasks:
                all_series = set(st.series for st in seriestasks)
            else:
                all_series = session.query(Series).all()
            for series in all_series:
                name = series.name
                # capitalize if user hasn't, better look and sorting ...
                if name.islower():
                    name = capwords(name)
                result[name] = {'identified_by': series.identified_by}
                result[name]['in_tasks'] = [task.name for task in series.in_tasks]
                episode = self.get_latest_download(series)
                if episode:
                    latest = {'first_seen': episode.first_seen,
                              'episode_instance': episode,
                              'episode_id': episode.identifier,
                              'age': episode.age,
                              'status': self.get_latest_status(episode),
                              'behind': self.new_eps_after(episode)}

                    result[name]['latest'] = latest
        finally:
            session.close()
        return result

    def get_latest_status(self, episode):
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

    def display_summary(self, discontinued=False):
        """
        Display series summary. ie --series
        :param discontinued: Whether to display active or discontinued series
        """

        formatting = ' %-30s %-10s %-10s %-20s'
        console(formatting % ('Name', 'Latest', 'Age', 'Downloaded'))
        console('-' * 79)

        hidden = 0
        for series_name, data in sorted((self.get_series_summary()).iteritems()):
            new_ep = ' '
            if len(series_name) > 30:
                series_name = series_name[:27] + '...'

            last_dl = data.get('latest', {})
            behind = last_dl.get('behind', 0)

            # Mark new eps
            if last_dl:
                if last_dl['first_seen'] > datetime.now() - timedelta(days=2):
                    new_ep = '>'
            # Determine whether to hide series. Never hide explicitly configured series.
            if not data.get('in_tasks'):
                if behind <= 3 and (last_dl and last_dl['first_seen'] < datetime.now() - timedelta(days=30 * 7)):
                    # Hide series that are have not been seen recently, and are not behind too many eps
                    hidden += 1
                    continue

            status = last_dl.get('status', 'N/A')
            age = last_dl.get('age', 'N/A')
            episode_id = last_dl.get('episode_id', 'N/A')
            if behind:
                episode_id += ' +%s' % last_dl['behind']

            console(new_ep + formatting[1:] % (series_name, episode_id, age if age else '', status))
            if behind >= 3:
                console(' ! Latest download is %d episodes behind, this may require '
                        'manual intervention' % behind)

        console('-' * 79)
        console(' > = new episode ' +
                ('| %i series unseen past 6 months hidden' % hidden if hidden else ''))
        console(' Use --series NAME to get detailed information')


class SeriesForget(object):
    """Provides --series-forget"""

    def on_process_start(self, task):
        if task.manager.options.series_forget:
            task.manager.disable_tasks()

            name = unicode(task.manager.options.series_forget[0])

            if len(task.manager.options.series_forget) > 1:
                # remove by id
                identifier = task.manager.options.series_forget[1]
                if identifier and name:
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

            task.manager.config_changed()


@event('manager.startup')
def series_begin(manager):
    if not manager.options.series_begin:
        return
    manager.disable_tasks()
    series_name, ep_id = manager.options.series_begin
    session = Session()
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


register_plugin(SeriesReport, '--series', builtin=True)
register_plugin(SeriesForget, '--series-forget', builtin=True)

register_parser_option('--series-begin', nargs=2, metavar=('NAME', 'EP_ID'),
                       help='Mark the first desired episode of a series. Episodes before this will not be grabbed')
register_parser_option('--series', nargs='?', const=True, help='Display series summary.')
register_parser_option('--series-forget', nargs='1-2', metavar=('NAME', 'EP_ID'),
                       help='Remove complete series or single episode from database: <NAME> [EPISODE]')
