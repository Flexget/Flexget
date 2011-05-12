from sqlalchemy.orm import join
from sqlalchemy import desc, func
from flexget.plugin import register_plugin, register_parser_option, DependencyError

try:
    from flexget.plugins.filter.series import SeriesPlugin, Series, Episode, Release, forget_series, forget_series_episode
except ImportError:
    raise DependencyError(issued_by='cli_series', missing='series', message='Series commandline interface not loaded')


class SeriesReport(SeriesPlugin):

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
        series = session.query(Series).filter(Series.name_lower == name.lower()).first()
        if not series:
            print 'Unknown series `%s`' % name
            return

        print ' %-63s%-15s' % ('Identifier, Title', 'Quality')
        print '-' * 79

        # Query episodes in sane order instead of iterating from series.episodes
        episodes = session.query(Episode).filter(Episode.series_id == series.id).\
            order_by(Episode.identifier).all()

        for episode in episodes:

            if episode.identifier is None:
                print ' None <--- Broken!'
            else:
                print ' %s - %s' % (episode.identifier, episode.age)

            for release in episode.releases:
                status = release.quality.name
                title = release.title
                if len(title) > 55:
                    title = title[:55] + '...'
                if release.proper_count:
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

    def display_summary(self):
        """Display series summary. ie --series"""

        print ' %-30s%-20s%-21s' % ('Name', 'Latest', 'Status')
        print '-' * 79

        from flexget.manager import Session
        session = Session()

        for series in session.query(Series).all():

            # get latest episode in episodic format
            episode = session.query(Episode).select_from(join(Episode, Series)).\
                      filter(Series.name_lower == series.name_lower).\
                      filter(Episode.season != None).\
                      order_by(desc(Episode.season)).\
                      order_by(desc(Episode.number)).first()

            # no luck, try uid format
            if not episode:
                episode = session.query(Episode).join(Series, Release).\
                          filter(Series.name_lower == series.name_lower).\
                          filter(Episode.season == None).\
                          order_by(desc(Release.first_seen)).first()

            latest = ''
            status = ''

            if episode:
                if not episode.season or not episode.number:
                    latest = '%s (id) - %s' % (episode.identifier, episode.age)
                else:
                    latest = 'S%sE%s - %s' % (str(episode.season).zfill(2), str(episode.number).zfill(2), episode.age)

                for release in self.get_releases(session, series.name, episode.identifier):
                    if release.downloaded:
                        status += '*'
                    status += release.quality.name
                    if release.proper_count:
                        status += '-proper'
                        if release.proper_count > 1:
                            status += str(release.proper_count)
                    status += ' '
            else:
                latest = 'N/A'
                status = 'N/A'

            print ' %-30s%-20s%-21s' % (series.name.title(), latest, status)

        print '-' * 79
        print ' * = downloaded'
        session.close()


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
