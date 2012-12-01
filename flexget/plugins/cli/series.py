from datetime import datetime, timedelta
from string import capwords
from sqlalchemy import desc
from flexget.manager import Session
from flexget.plugin import register_plugin, register_parser_option, DependencyError
from flexget.utils.tools import console

try:
    from flexget.plugins.filter.series import SeriesDatabase, Series, Episode, Release, forget_series, forget_series_episode
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

        name = unicode(name.lower())
        series = session.query(Series).filter(Series.name == name).first()
        if not series:
            console('Unknown series `%s`' % name)
            return

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
        result = {}
        session = Session()
        try:
            for series in session.query(Series).all():
                name = unicode(series.name)
                # capitalize if user hasn't, better look and sorting ...
                if name.islower():
                    name = capwords(name)
                result[name] = {'identified_by': series.identified_by}
                episode = self.latest_seen_episode(session, series)
                if episode:
                    latest = {'first_seen': episode.first_seen,
                              'episode_instance': episode,
                              'episode_id': episode.identifier,
                              'age': episode.age,
                              'status': self.get_latest_status(episode)}
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

    def latest_seen_episode(self, session, series):
        """
        :param session: SQLAlchemy session
        :param series: Instance of Series
        :return: Instance of latest Episode or None
        """
        return session.query(Episode).join(Series, Release).\
                    filter(Series.id == series.id).\
                    order_by(desc(Release.first_seen)).first()

    def display_summary(self, discontinued=False):
        """
        Display series summary. ie --series
        :param discontinued: Whether to display active or discontinued series
        """

        formatting = ' %-30s %-10s %-10s %-20s'
        console(formatting % ('Name', 'Latest', 'Age', 'Downloaded'))
        console('-' * 79)

        hidden = 0
        series = self.get_series_summary()
        for series_name, data in sorted(series.iteritems()):
            new_ep = ' '
            if len(series_name) > 30:
                series_name = series_name[:27] + '...'

            if 'latest' in data:
                if data['latest']['first_seen'] > datetime.now() - timedelta(days=2):
                    new_ep = '>'
                if data['latest']['first_seen'] < datetime.now() - timedelta(days=30 * 7):
                    hidden += 1
                    continue

            latest = data.get('latest', {})
            status = latest.get('status', 'N/A')
            age = latest.get('age', 'N/A')
            episode_id = latest.get('episode_id', 'N/A')

            console(new_ep + formatting[1:] % (series_name, episode_id, age if age else '', status))

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
                identifier = task.manager.options.series_forget[1].upper()
                if identifier and name:
                    try:
                        forget_series_episode(name, identifier)
                        console('Removed episode `%s` from series `%s`.' % (identifier, name.capitalize()))
                    except ValueError, e:
                        console(e.message)
            else:
                # remove whole series
                try:
                    forget_series(name)
                    console('Removed series `%s` from database.' % name.capitalize())
                except ValueError, e:
                    console(e.message)

            task.manager.config_changed()


register_plugin(SeriesReport, '--series', builtin=True)
register_plugin(SeriesForget, '--series-forget', builtin=True)

register_parser_option('--series', nargs='?', const=True, help='Display series summary.')
register_parser_option('--series-forget', nargs='1-2', metavar=('NAME', 'EP_ID'),
                       help='Remove complete series or single episode from database: <NAME> [EPISODE]')
