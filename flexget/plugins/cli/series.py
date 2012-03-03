from datetime import datetime, timedelta
from flexget.manager import Session
from string import capwords
from sqlalchemy.orm import join
from sqlalchemy import desc
from flexget.plugin import register_plugin, register_parser_option, DependencyError

try:
    from flexget.plugins.filter.series import SeriesDatabase, Series, Episode, Release, forget_series, forget_series_episode
except ImportError:
    raise DependencyError(issued_by='cli_series', missing='series', message='Series commandline interface not loaded')


class SeriesReport(SeriesDatabase):

    """Produces --series report"""

    options = {}

    @staticmethod
    def optik_series(option, opt, value, parser):
        """--series [NAME]"""
        SeriesReport.options['got'] = True
        if parser.rargs:
            SeriesReport.options['name'] = parser.rargs[0]

    def on_process_start(self, feed):
        if self.options:
            feed.manager.disable_feeds()

            if not 'name' in self.options:
                self.display_summary()
            else:
                self.display_details()

    def display_details(self):
        """Display detailed series information, ie. --series NAME"""

        from flexget.manager import Session
        session = Session()

        name = unicode(self.options['name'].lower())
        series = session.query(Series).filter(Series.name == name).first()
        if not series:
            print 'Unknown series `%s`' % name
            return

        print '%s is in identified_by `%s` mode.' % (series.name, series.identified_by or 'auto')

        print ' %-63s%-15s' % ('Identifier, Title', 'Quality')
        print '-' * 79

        # Query episodes in sane order instead of iterating from series.episodes
        episodes = session.query(Episode).filter(Episode.series_id == series.id).\
            order_by(Episode.identifier).all()

        for episode in episodes:

            if episode.identifier is None:
                print ' None <--- Broken!'
            else:
                print ' %s (%s) - %s' % (episode.identifier, episode.identified_by, episode.age)

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
                    print '  * %-60s%-15s' % (title, status)
                else:
                    print '    %-60s%-15s' % (title, status)

        print '-' * 79
        print ' * = downloaded'
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
            if release.downloaded:
                status += '['
            status += release.quality.name
            if release.proper_count > 0:
                status += '-proper'
                if release.proper_count > 1:
                    status += str(release.proper_count)
            if release.downloaded:
                status += ']'
            status += ' '
        return status if status else None

    def latest_seen_episode(self, session, series):
        """
        :param session: SQLAlchemy session
        :param series: Instance of Series
        :return: Instance of latest Episode or None
        """
        episode = None
        # try to get latest episode in episodic format
        if series.identified_by in ('ep', 'auto', None):
            episode = session.query(Episode).select_from(join(Episode, Series)).\
                filter(Series.id == series.id).\
                filter(Episode.season != None).\
                order_by(desc(Episode.season)).\
                order_by(desc(Episode.number)).first()
        # no luck, try uid format
        if series.identified_by in ('id', 'auto', None):
            if not episode:
                episode = session.query(Episode).join(Series, Release).\
                    filter(Series.id == series.id).\
                    filter(Episode.season == None).\
                order_by(desc(Release.first_seen)).first()
        return episode

    def display_summary(self, discontinued=False):
        """
        Display series summary. ie --series
        :param discontinued: Whether to display active or discontinued series
        """

        formatting = ' %-30s %-10s %-10s %-20s'
        print formatting % ('Name', 'Latest', 'Age', 'Status')
        print '-' * 79

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

            print new_ep + formatting[1:] % (series_name, episode_id, age if age else '', status)

        print '-' * 79
        print ' [] = downloaded | > = new episode %s' % \
              '| %i series unseen past 6 months hidden' % hidden if hidden else ''
        print ' Use --series NAME to get detailed information'


class SeriesForget(object):

    """Provides --series-forget"""

    options = {}

    @staticmethod
    def optik_series_forget(option, opt, value, parser):
        """
        Callback for Optik
        --series-forget NAME [ID]
        """
        if not parser.rargs:
            return # how to handle invalid?
        if len(parser.rargs) > 0:
            SeriesForget.options['name'] = parser.rargs[0]
        if len(parser.rargs) > 1:
            SeriesForget.options['episode'] = parser.rargs[1]

    def on_process_start(self, feed):
        if self.options:
            feed.manager.disable_feeds()

            name = unicode(self.options.get('name'))

            if self.options.get('episode'):
                # remove by id
                identifier = self.options.get('episode').upper()
                if identifier and name:
                    try:
                        forget_series_episode(name, identifier)
                        print 'Removed episode `%s` from series `%s`.' % (identifier, name.capitalize())
                    except ValueError, e:
                        print e.message
            else:
                # remove whole series
                try:
                    forget_series(name)
                    print 'Removed series `%s` from database.' % name.capitalize()
                except ValueError, e:
                    print e.message


register_plugin(SeriesReport, '--series', builtin=True)
register_plugin(SeriesForget, '--series-forget', builtin=True)

register_parser_option('--series', action='callback', callback=SeriesReport.optik_series,
                       help='Display series summary.')
register_parser_option('--series-forget', action='callback', callback=SeriesForget.optik_series_forget,
                       help='Remove complete series or single episode from database: <NAME> [EPISODE]')
