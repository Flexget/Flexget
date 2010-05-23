import logging
from datetime import datetime, timedelta
from flexget.utils.titles import SeriesParser, ParseWarning
from flexget.utils import qualities
from flexget.manager import Base
from flexget.plugin import *
from sqlalchemy import Column, Integer, String, Unicode, DateTime, Boolean, desc
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation, join

log = logging.getLogger('series')


class Series(Base):

    __tablename__ = 'series'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)
    episodes = relation('Episode', backref='series', cascade='all, delete, delete-orphan')

    def __repr__(self):
        return '<Series(name=%s)>' % (self.name)


class Episode(Base):

    __tablename__ = 'series_episodes'

    id = Column(Integer, primary_key=True)
    identifier = Column(String)
    first_seen = Column(DateTime)

    season = Column(Integer)
    number = Column(Integer)

    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)
    releases = relation('Release', backref='episode', cascade='all, delete, delete-orphan')

    @property
    def age(self):
        diff = datetime.now() - self.first_seen
        age_days = diff.days
        age_hours = diff.seconds / 60 / 60
        age = ''
        if age_days:
            age += '%sd ' % age_days
        age += '%sh' % age_hours
        return age

    def __init__(self):
        self.first_seen = datetime.now()

    def __repr__(self):
        return '<Episode(identifier=%s)>' % (self.identifier)


class Release(Base):

    __tablename__ = 'episode_releases'

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey('series_episodes.id'), nullable=False)
    quality = Column(String)
    downloaded = Column(Boolean, default=False)
    proper = Column(Boolean, default=False)
    title = Column(Unicode)

    def __repr__(self):
        return '<Release(quality=%s,downloaded=%s,proper=%s,title=%s)>' % \
            (self.quality, self.downloaded, self.proper, self.title)


class SeriesPlugin(object):

    """Database helpers"""

    def get_first_seen(self, session, parser):
        """Return datetime when this episode of series was first seen"""
        episode = session.query(Episode).select_from(join(Episode, Series)).\
            filter(Series.name == parser.name.lower()).filter(Episode.identifier == parser.identifier).first()
        if not episode:
            log.log(5, '%s not seen, return current time' % parser)
            return datetime.now()
        return episode.first_seen

    def get_latest_info(self, session, name):
        """Return latest known identifier in dict (season, episode, name) for series name"""
        episode = session.query(Episode).select_from(join(Episode, Series)).\
            filter(Episode.season != None).\
            filter(Series.name == name.lower()).\
            order_by(desc(Episode.season)).\
            order_by(desc(Episode.number)).first()
        if not episode:
            #log.log(5, 'get_latest_info: no info available for %s' % name)
            return False
        #log.log(5, 'get_latest_info, series: %s season: %s episode: %s' % \
        #    (name, episode.season, episode.number))
        return {'season': episode.season, 'episode': episode.number, 'name': name}

    def identified_by_ep(self, session, name, min=4, min_percent=50):
        """Determine if series :name: should be considered episodic"""
        series = session.query(Series).filter(Series.name == name).first()
        if not series:
            return False

        total = len(series.episodes)
        if total < min:
            return False
        episodic = 0
        for episode in series.episodes:
            if episode.season and episode.number:
                episodic += 1
        percent = (float(episodic) / float(total)) * 100
        log.debug('series %s episodic check: %s/%s (%s percent)' % (name, episodic, total, percent))
        if percent > min_percent:
            return True

    def identified_by_id(self, session, name, min=4, min_percent=50):
        """Determine if series :name: should be considered identified by id"""
        series = session.query(Series).filter(Series.name == name).first()
        if not series:
            return False

        total = len(series.episodes)
        if total < min:
            return False
        non_episodic = 0
        for episode in series.episodes:
            if not episode.season and not episode.number:
                non_episodic += 1
        percent = (float(non_episodic) / float(total)) * 100
        log.debug('series %s id-format check: %s/%s (%s percent)' % (name, non_episodic, total, percent))
        if percent > min_percent:
            return True

    def get_latest_download(self, session, name):
        """Return latest downloaded episode (season, episode, name) for series name"""
        series = session.query(Series).filter(Series.name == name).first()
        if not series:
            log.debug('get_latest_download returning false, series %s does not exists' % name)
            return False

        latest_season = 0
        latest_episode = 0

        def episode_downloaded(episode):
            for release in episode.releases:
                if release.downloaded:
                    return True

        for episode in series.episodes:
            if episode_downloaded(episode) and episode.season >= latest_season and episode.number > latest_episode:
                latest_season = episode.season
                latest_episode = episode.number

        if latest_season == 0 or latest_episode == 0:
            log.debug('get_latest_download returning false, latest_season: %s latest_episode: %s' % (latest_season, latest_episode))
            return False

        return {'season': latest_season, 'episode': latest_episode, 'name': name}

    def get_releases(self, session, name, identifier):
        """Return all releases for series by identifier."""
        episode = session.query(Episode).select_from(join(Episode, Series)).\
            filter(Series.name == name.lower()).\
            filter(Episode.identifier == identifier).first()
        if not episode:
            return []
        releases = []
        for release in session.query(Release).filter(Release.episode_id == episode.id).\
            order_by(desc(Release.quality)).all():
            releases.append(release)
        return releases

    def get_downloaded(self, session, name, identifier):
        """Return list of downloaded releases for this episode"""
        episode = session.query(Episode).select_from(join(Episode, Series)).\
            filter(Series.name == name.lower()).\
            filter(Episode.identifier == identifier).first()
        if not episode:
            log.debug('get_downloaded: episode or series does not exist')
            return []
        downloaded = []
        for release in session.query(Release).filter(Release.episode_id == episode.id).\
            filter(Release.downloaded == True).all():
            downloaded.append(release)
        if not downloaded:
            log.debug('get_downloaded: no %s downloads recorded for %s' % (identifier, name))
        return downloaded

    def store(self, session, parser):
        """Push series information into database. Returns added/existing release."""
        # if series does not exist in database, add new
        series = session.query(Series).filter(Series.name == parser.name.lower()).first()
        if not series:
            log.debug('adding series %s into db' % parser.name)
            series = Series()
            series.name = parser.name.lower()
            session.add(series)
            log.debug('-> added %s' % series)

        # if episode does not exist in series, add new
        episode = session.query(Episode).filter(Episode.series_id == series.id).\
            filter(Episode.identifier == parser.identifier).first()
        if not episode:
            log.debug('adding episode %s into series %s' % (parser.identifier, parser.name))
            episode = Episode()
            episode.identifier = parser.identifier
            # if episodic format
            if parser.season and parser.episode:
                episode.season = parser.season
                episode.number = parser.episode
            series.episodes.append(episode) # pylint: disable-msg=E1103
            log.debug('-> added %s' % episode)

        # if release does not exists in episodes, add new
        #
        # NOTE:
        #
        # filter(Release.episode_id != None) fixes weird bug where release had/has been added
        # to database but doesn't have episode_id, this causes all kinds of havoc with the plugin.
        # perhaps a bug in sqlalchemy?
        release = session.query(Release).filter(Release.episode_id == episode.id).\
            filter(Release.episode_id != None).\
            filter(Release.quality == parser.quality).\
            filter(Release.proper == parser.proper_or_repack).first()
        if not release:
            log.debug('addding release %s into episode' % parser)
            release = Release()
            release.quality = parser.quality
            release.proper = parser.proper_or_repack
            release.title = parser.data
            episode.releases.append(release) # pylint: disable-msg=E1103
            log.debug('-> added %s' % release)
        return release


class SeriesReport(SeriesPlugin):

    """Produces --series report"""

    options = {}

    @staticmethod
    def optik_series(option, opt, value, parser):
        """--series [NAME]"""
        SeriesReport.options['got'] = True
        if len(parser.rargs) != 0:
            SeriesReport.options['name'] = parser.rargs[0]

    def on_process_start(self, feed):
        if self.options:
            feed.manager.disable_feeds()

            if not 'name' in self.options:
                self.display_summary()
            else:
                self.display_details()

    def display_details(self):
        """Display detailed series information"""
        from flexget.manager import Session

        session = Session()

        name = unicode(self.options['name'].lower())
        series = session.query(Series).filter(Series.name == name.lower()).first()
        if not series:
            print 'Unknown series %s' % name
            return

        print ' %-63s%-15s' % ('Identifier, Title', 'Quality')
        print '-' * 79

        for episode in series.episodes:

            if episode.identifier is None:
                print ' None <--- Broken!'
            else:
                print ' %s - %s' % (episode.identifier, episode.age)

            for release in episode.releases:
                status = release.quality
                title = release.title
                if len(title) > 55:
                    title = title[:55] + '...'
                if release.proper:
                    status += '-Proper'
                if release.downloaded:
                    print '  * %-60s%-15s' % (title, status)
                else:
                    print '    %-60s%-15s' % (title, status)

        print '-' * 79
        print ' * = downloaded'
        session.close()

    def display_summary(self):
        """Display series summary"""
        print ' %-30s%-20s%-21s' % ('Name', 'Latest', 'Status')
        print '-' * 79

        from flexget.manager import Session
        session = Session()

        for series in session.query(Series).all():

            # get latest episode in episodic format
            episode = session.query(Episode).select_from(join(Episode, Series)).\
                      filter(Series.name == series.name.lower()).filter(Episode.season != None).\
                      order_by(desc(Episode.season)).order_by(desc(Episode.number)).first()

            # no luck, try uid format
            if not episode:
                episode = session.query(Episode).select_from(join(Episode, Series)).\
                          filter(Series.name == series.name.lower()).filter(Episode.season == None).\
                          order_by(desc(Episode.first_seen)).first()

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
                    status += release.quality
                    if release.proper:
                        status += '-Proper'
                    status += ' '
            else:
                latest = 'N/A'
                status = 'N/A'

            print ' %-30s%-20s%-21s' % (series.name.capitalize(), latest, status)

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
        if len(parser.rargs) == 0:
            return # how to handle invalid?
        if len(parser.rargs) > 0:
            SeriesForget.options['name'] = parser.rargs[0]
        if len(parser.rargs) > 1:
            SeriesForget.options['episode'] = parser.rargs[1]

    def on_process_start(self, feed):
        if self.options:
            feed.manager.disable_feeds()

            name = unicode(self.options.get('name'))

            from flexget.manager import Session
            session = Session()

            if self.options.get('episode'):
                # remove by id
                identifier = self.options.get('episode').upper()
                if identifier and name:
                    series = session.query(Series).filter(Series.name == name.lower()).first()
                    if series:
                        episode = session.query(Episode).filter(Episode.identifier == identifier).\
                            filter(Episode.series_id == series.id).first()
                        if episode:
                            print 'Removed %s %s' % (name.capitalize(), identifier)
                            log.debug('episode: %s' % episode)
                            for rel in episode.releases:
                                log.debug('release: %s' % rel)
                            session.delete(episode)
                        else:
                            print 'Didn\'t find %s episode identified by %s' % (name.capitalize(), identifier)
                    else:
                        print 'Unknown series %s' % name
            else:
                # remove whole series
                series = session.query(Series).\
                         filter(Series.name == name.lower()).first()
                if series:
                    print 'Removed %s' % name
                    session.delete(series)
                else:
                    print 'Unknown series %s' % name

            session.commit()


class FilterSeries(SeriesPlugin):

    """
        Intelligent filter for tv-series.

        http://flexget.com/wiki/FilterSeries
    """

    def __init__(self):
        self.parser2entry = {}
        self.backlog = None

    def on_process_start(self, feed):

        try:
            self.backlog = get_plugin_by_name('backlog').instance
        except:
            log.warning('Unable utilize backlog plugin, episodes may slip trough timeframe')

    def validator(self):
        from flexget import validator

        def build_options(options):
            options.accept('text', key='path')
            # set
            options.accept('dict', key='set').accept_any_key('any')
            # regexes can be given in as a single string ..
            options.accept('regexp', key='name_regexp')
            options.accept('regexp', key='ep_regexp')
            options.accept('regexp', key='id_regexp')
            # .. or as list containing strings
            options.accept('list', key='name_regexp').accept('regexp')
            options.accept('list', key='ep_regexp').accept('regexp')
            options.accept('list', key='id_regexp').accept('regexp')
            # quality
            options.accept('text', key='quality')                    # TODO: allow only SeriesParser.qualities
            options.accept('list', key='qualities').accept('text')   # TODO: ^^
            options.accept('text', key='min_quality')                # TODO: ^^
            options.accept('text', key='max_quality')                # TODO: ^^
            # propers
            options.accept('boolean', key='propers')
            options.accept('regexp_match', key='propers').accept('\d+ (minutes|hours|days|weeks)')
            # expect flags
            options.accept('text', key='identified_by')
            # timeframe
            options.accept('regexp_match', key='timeframe').accept('\d+ (minutes|hours|days|weeks)')
            # strict naming
            options.accept('boolean', key='exact')
            # watched
            watched = options.accept('dict', key='watched')
            watched.accept('number', key='season')
            watched.accept('number', key='episode')
            # from group
            options.accept('text', key='from_group')

        def build_list(series):
            """Build series list to series."""
            series.accept('text')
            series.accept('number')
            bundle = series.accept('dict')
            # prevent invalid indentation level
            bundle.reject_keys(['set', 'path', 'timeframe', 'name_regexp',
                'ep_regexp', 'id_regexp', 'watched', 'quality', 'min_quality',
                'max_quality', 'qualities', 'exact', 'from_group'],
                'Option \'$key\' has invalid indentation level. It needs 2 more spaces.')
            bundle.accept_any_key('path')
            options = bundle.accept_any_key('dict')
            build_options(options)

        root = validator.factory()

        # simple format:
        #   - series
        #   - another series

        simple = root.accept('list')
        build_list(simple)

        # advanced format:
        #   settings:
        #     group: {...}
        #   group:
        #     {...}

        advanced = root.accept('dict')
        settings = advanced.accept('dict', key='settings')
        settings.reject_keys(get_plugin_keywords())
        settings_group = settings.accept_any_key('dict')
        build_options(settings_group)

        group = advanced.accept_any_key('list')
        build_list(group)

        return root

    def on_feed_input(self, feed):
        if self.backlog:
            self.backlog.inject_backlog(feed)

    def generate_config(self, feed):
        """Generate configuration dictionary from configuration. Converts simple format into advanced.
        This way we don't need to handle two different configuration formats in the logic.
        Applies group settings with advanced form."""

        feed_config = feed.config.get('series', [])

        # generate unified configuration in complex form, requires complex code as well :)
        config = {}
        if isinstance(feed_config, list):
            # convert simplest configuration internally grouped format
            config['settings'] = {}
            config['simple'] = []
            for series in feed_config:
                # convert into dict-form if necessary
                series_settings = {}
                if isinstance(series, dict):
                    series, series_settings = series.items()[0]
                    if series_settings is None:
                        raise Exception('Series %s has unexpected \':\'' % series)
                config['simple'].append({series: series_settings})
        else:
            # already in grouped format, just get settings from there
            import copy
            config = copy.deepcopy(feed_config)
            if not 'settings' in config:
                config['settings'] = {}

        # TODO: what if same series is configured in multiple groups?!

        # generate quality settings from group name and empty settings if not present (required)
        for group_name, _ in config.iteritems():
            if group_name == 'settings':
                continue
            if not group_name in config['settings']:
                # at least empty settings
                config['settings'][group_name] = {}
                # if known quality, convenience create settings with that quality
                if group_name in qualities.registry:
                    config['settings'][group_name]['quality'] = group_name

        # generate groups from settings groups
        for group_name, group_settings in config['settings'].iteritems():
            # convert group series into complex types
            complex_series = []
            for series in config.get(group_name, []):
                # convert into dict-form if necessary
                series_settings = {}
                if isinstance(series, dict):
                    series, series_settings = series.items()[0]
                    if series_settings is None:
                        raise Exception('Series %s has unexpected \':\'' % series)
                # make sure series name is a string to accomadate for "24"
                if not isinstance(series, basestring):
                    series = str(series)
                # if series have given path instead of dict, convert it into a dict
                if isinstance(series_settings, basestring):
                    series_settings = {'path': series_settings}
                # merge group settings into this series settings
                from flexget.utils.tools import merge_dict_from_to
                merge_dict_from_to(group_settings, series_settings)
                complex_series.append({series: series_settings})
            # add generated complex series into config
            config[group_name] = complex_series

        # settings is not needed anymore, just confuses
        del(config['settings'])
        return config

    def auto_exact(self, config):
        """Automatically enable exact naming option for series that look like a problem"""

        # generate list of all series in one dict
        all_series = {}
        for group_series in config.itervalues():
            for series_item in group_series:
                series_name, series_config = series_item.items()[0]
                all_series[series_name] = series_config

        # scan for problematic names, enable exact mode for them
        for series_name, series_config in all_series.iteritems():
            for name in all_series.keys():
                if (name.lower().startswith(series_name.lower())) and \
                   (name.lower() != series_name.lower()):
                    if not 'exact' in series_config:
                        log.info('Auto enabling exact matching for series %s (reason %s)' % (series_name, name))
                        series_config['exact'] = True

    def on_feed_filter(self, feed):
        """Filter series"""

        # TEMP: bugfix, convert all series to lowercase
        for series in feed.session.query(Series).all():
            series.name = series.name.lower()

        config = self.generate_config(feed)
        self.auto_exact(config)

        for group_series in config.itervalues():
            for series_item in group_series:
                series_name, series_config = series_item.items()[0]
                # yaml loads ascii only as str
                series_name = unicode(series_name)
                log.log(5, 'series_name: %s series_config: %s' % (series_name, series_config))

                import time
                start_time = time.clock()

                series = self.parse_series(feed, series_name, series_config)
                self.process_series(feed, series, series_name, series_config)

                took = time.clock() - start_time
                log.log(5, 'processing %s took %s' % (series_name, took))

    def parse_series(self, feed, series_name, config):
        """
            Search for :series_name: and return dict containing all episodes from it
            in a dict where key is the episode identifier and value is a list of episodes
            in form of SeriesParser.
        """

        def get_as_array(config, key):
            """Return configuration key as array, even if given as a single string"""
            v = config.get(key, [])
            if isinstance(v, basestring):
                return [v]
            return v

        # expect flags

        expect_ep = False
        expect_id = False

        identified_by = config.get('identified_by', 'auto')
        if identified_by not in ['ep', 'id', 'auto']:
            raise PluginError('Unknown identified_by value %s for the series %s' % (identified_by, series_name))

        if 'identified_by' == 'auto':
            # set expect flags automatically

            # determine if series is known to be in season, episode format or identified by id
            expect_ep = self.identified_by_ep(feed.session, series_name)
            expect_id = self.identified_by_id(feed.session, series_name)

            # in case identified by both, we have a unresolvable situation
            if expect_ep and expect_id:
                log.critical('Series %s cannot be determined to be either episodic or identified by id, ' % series_name +
                             'you should specify `identified_by` (ep|id) for it!')
                expect_ep = False
                expect_id = False
        else:
            # set expect flags manually from config
            expect_ep = identified_by == 'ep'
            expect_id = identified_by == 'id'

        # helper function, iterate entry fields in certain order
        def field_order(a, b):
            order = ['title', 'description']

            def index(c):
                try:
                    return order.index(c[0])
                except ValueError:
                    return 1

            return cmp(index(a), index(b))

        # don't try to parse these fields
        ignore_fields = ['uid', 'feed', 'url', 'original_url']

        # key: series (episode) identifier ie. S01E02
        # value: seriesparser
        series = {}
        for entry in feed.entries:
            for field, data in sorted(entry.items(), cmp=field_order):
                # skip invalid fields
                if not isinstance(data, basestring) or not data:
                    continue
                # skip ignored
                if field in ignore_fields:
                    continue
                parser = SeriesParser()
                parser.name = series_name
                parser.data = data
                parser.expect_ep = expect_ep
                parser.expect_id = expect_id
                parser.ep_regexps = get_as_array(config, 'ep_regexp') + parser.ep_regexps
                parser.id_regexps = get_as_array(config, 'id_regexp') + parser.id_regexps
                parser.strict_name = config.get('exact', False)
                parser.from_group = config.get('from_group', None)
                parser.field = field
                # do not use builtin list for id when ep configured and vice versa
                if 'ep_regexp' in config and not 'id_regexp' in config:
                    parser.id_regexps = []
                if 'id_regexp' in config and not 'ep_regexp' in config:
                    parser.ep_regexps = []
                parser.name_regexps.extend(get_as_array(config, 'name_regexp'))
                try:
                    parser.parse()
                except ParseWarning, pw:
                    from flexget.utils.log import log_once
                    log_once(pw.value, logger=log)

                if parser.valid:
                    log.debug('%s detected as %s, field: %s' % (entry['title'], parser, parser.field))
                    self.parser2entry[parser] = entry
                    entry['series_parser'] = parser
                    break
            else:
                continue

            # add series, season and episode to entry
            entry['series_name'] = series_name
            if parser.season and parser.episode:
                entry['series_season'] = parser.season
                entry['series_episode'] = parser.episode
            else:
                import time
                entry['series_season'] = time.gmtime().tm_year
            entry['series_id'] = parser.identifier

            # set custom download path
            if 'path' in config:
                log.debug('setting %s custom path to %s' % (entry['title'], config.get('path')))
                entry['path'] = config.get('path') % entry

            # accept info from set: and place into the entry
            if 'set' in config:
                set = get_plugin_by_name('set')
                set.instance.modify(entry, config.get('set'))

            # add this episode into list of available episodes
            eps = series.setdefault(parser.identifier, [])
            eps.append(parser)

            # store this episode into database and save reference for later use
            release = self.store(feed.session, parser)
            entry['series_release'] = release

        return series

    def process_series(self, feed, series, series_name, config):
        """Accept or Reject episode from available releases, or postpone choosing."""
        for eps in series.itervalues():
            whitelist = []

            # sort episodes in order of quality
            eps.sort(reverse=True)

            log.debug('start with episodes: %s' % [e.data for e in eps])

            # reject episodes that have been marked as watched in config file
            if 'watched' in config:
                log.debug('-' * 20 + ' watched -->')
                if self.process_watched(feed, config, eps):
                    continue

            # proper handling
            log.debug('-' * 20 + ' process_propers -->')
            removed, new_propers = self.process_propers(feed, config, eps)
            whitelist.extend(new_propers)

            for ep in removed:
                log.debug('propers removed: %s' % ep)
                eps.remove(ep)

            if not eps:
                continue

            log.debug('-' * 20 + ' accept_propers -->')
            accepted = self.accept_propers(feed, eps, whitelist)
            whitelist.extend(accepted)

            log.debug('current episodes: %s' % [e.data for e in eps])

            # qualities
            if 'qualities' in config:
                log.debug('-' * 20 + ' process_qualities -->')
                self.process_qualities(feed, config, eps, whitelist)
                continue

            # reject downloaded
            log.debug('-' * 20 + ' downloaded -->')
            for ep in self.process_downloaded(feed, eps, whitelist):
                feed.reject(self.parser2entry[ep], 'already downloaded')
                log.debug('downloaded removed: %s' % ep)
                eps.remove(ep)

            # no episodes left, continue to next series
            if not eps:
                continue

            best = eps[0]
            log.debug('continuing w. episodes: %s' % [e.data for e in eps])
            log.debug('best episode is: %s' % best.data)

            # episode advancement. used only with season based series
            if best.season and best.episode:
                log.debug('-' * 20 + ' episode advancement -->')
                if self.process_episode_advancement(feed, eps, series):
                    continue

            # timeframe
            if 'timeframe' in config:
                log.debug('-' * 20 + ' timeframe -->')
                self.process_timeframe(feed, config, eps, series_name)
                continue

            # quality, min_quality, max_quality and NO timeframe
            if ('timeframe' not in config and 'qualities' not in config) and \
               ('quality' in config or 'min_quality' in config or 'max_quality' in config):
                log.debug('-' * 20 + ' process quality -->')
                self.process_quality(feed, config, eps)
                continue

            # no special configuration, just choose the best
            reason = 'only choice'
            if len(eps) > 1:
                reason = 'choose best'
            self.accept_series(feed, best, reason)

    def process_propers(self, feed, config, eps):
        """
            Rejects downloaded propers, nukes episodes from which there exists proper.
            Returns a list of removed episodes and a list of new propers.
        """

        downloaded_releases = self.get_downloaded(feed.session, eps[0].name, eps[0].identifier)
        downloaded_qualities = [d.quality for d in downloaded_releases]

        log.debug('downloaded qualities: %s' % downloaded_qualities)

        def proper_downloaded():
            for release in downloaded_releases:
                if release.proper:
                    return True


        new_propers = []
        removed = []
        for ep in eps:
            if ep.proper_or_repack:
                if not proper_downloaded():
                    log.debug('found new proper %s' % ep)
                    new_propers.append(ep)
                else:
                    feed.reject(self.parser2entry[ep], 'proper already downloaded')
                    removed.append(ep)

        if downloaded_qualities:
            for proper in new_propers[:]:
                if proper.quality not in downloaded_qualities:
                    log.debug('proper %s quality missmatch' % proper)
                    new_propers.remove(proper)

        # nuke qualities which there is proper available
        for proper in new_propers:
            for ep in set(eps) - set(removed) - set(new_propers):
                if ep.quality == proper.quality:
                    feed.reject(self.parser2entry[ep], 'nuked')
                    removed.append(ep)

        # nuke propers after timeframe
        if 'propers' in config:
            if isinstance(config['propers'], bool):
                if not config['propers']:
                    # no propers
                    for proper in new_propers[:]:
                        feed.reject(self.parser2entry[proper], 'no propers')
                        removed.append(proper)
                        new_propers.remove(proper)
            else:
                # propers with timeframe
                amount, unit = config['propers'].split(' ')
                log.debug('amount: %s unit: %s' % (repr(amount), repr(unit)))
                params = {unit: int(amount)}
                try:
                    timeframe = timedelta(**params)
                except TypeError:
                    raise PluginWarning('Invalid time format', log)

                first_seen = self.get_first_seen(feed.session, eps[0])
                expires = first_seen + timeframe
                log.debug('propers timeframe: %s' % timeframe)
                log.debug('first_seen: %s' % first_seen)
                log.debug('propers ignore after: %s' % str(expires))

                if datetime.now() > expires:
                    log.debug('propers timeframe expired')
                    for proper in new_propers[:]:
                        feed.reject(self.parser2entry[proper], 'propers timeframe expired')
                        removed.append(proper)
                        new_propers.remove(proper)

        log.debug('new_propers: %s' % [e.data for e in new_propers])
        return removed, new_propers

    def accept_propers(self, feed, eps, new_propers):
        """
            Accepts all propers from qualities already downloaded.
            :return: list of accepted
        """

        downloaded_releases = self.get_downloaded(feed.session, eps[0].name, eps[0].identifier)
        downloaded_qualities = [d.quality for d in downloaded_releases]

        accepted = []

        for proper in new_propers:
            if proper.quality in downloaded_qualities:
                log.debug('we\'ve downloaded quality %s, accepting proper from it' % proper.quality)
                feed.accept(self.parser2entry[proper], 'proper')
                accepted.append(proper)

        return accepted

    def process_downloaded(self, feed, eps, whitelist):
        """
            Rejects all downloaded episodes (regardless of quality).
            Doesn't reject reject anything in :whitelist:.
        """

        downloaded = []
        downloaded_releases = self.get_downloaded(feed.session, eps[0].name, eps[0].identifier)
        log.debug('downloaded: %s' % [e.title for e in downloaded_releases])
        if downloaded_releases and eps:
            log.debug('identifier %s is downloaded' % eps[0].identifier)
            for ep in eps[:]:
                if ep not in whitelist:
                    # same episode can appear multiple times, so add it just once to the list
                    if ep not in downloaded:
                        downloaded.append(ep)
        return downloaded

    def process_quality(self, feed, config, eps):
        """Accepts episodes that meet configured qualities"""

        min = qualities.min()
        max = qualities.max()
        if 'quality' in config:
            quality = qualities.get(config['quality'])
            min, max = quality, quality
        else:
            min_name = config.get('min_quality', qualities.min().name)
            max_name = config.get('max_quality', qualities.max().name)
            if min_name.lower() not in qualities.registry:
                raise PluginError('Unknown quality %s' % min_name)
            if max_name.lower() not in qualities.registry:
                raise PluginError('Unknown quality %s' % max_name)
            log.debug('min_name: %s max_name: %s' % (min_name, max_name))
            # get range
            min = qualities.get(min_name)
            max = qualities.get(max_name)
        # see if any of the eps match accepted qualities
        for ep in eps:
            quality = qualities.get(ep.quality)
            log.debug('ep: %s min: %s max: %s quality: %s' % (ep.data, min.value, max.value, quality.value))
            if quality <= max and quality >= min:
                self.accept_series(feed, ep, 'meets quality')
                break
        else:
            log.debug('no quality meets requirements')

    def process_watched(self, feed, config, eps):
        """Rejects all episodes older than defined in watched, returns True when this happens."""

        from sys import maxint
        best = eps[0]
        wconfig = config.get('watched')
        season = wconfig.get('season', -1)
        episode = wconfig.get('episode', maxint)
        if best.season < season or (best.season == season and best.episode <= episode):
            log.debug('%s episode %s is already watched, rejecting all occurrences' % (best.name, best.identifier))
            for ep in eps:
                entry = self.parser2entry[ep]
                feed.reject(entry, 'watched')
            return True

    def process_episode_advancement(self, feed, eps, series):
        """Rjects all episodes that are too old or new (advancement), return True when this happens."""

        current = eps[0]
        latest = self.get_latest_download(feed.session, current.name)
        log.debug('latest download: %s' % latest)
        log.debug('current: %s' % current)

        if latest:
            # allow few episodes "backwards" in case of missed eps
            grace = len(series) + 2
            if (current.season < latest['season']) or (current.season == latest['season'] and current.episode < (latest['episode'] - grace)):
                log.debug('too old! rejecting all occurrences')
                for ep in eps:
                    feed.reject(self.parser2entry[ep], 'too much in the past from latest downloaded episode S%02dE%02d' % (latest['season'], latest['episode']))
                return True

            if (current.season > latest['season'] + 1):
                log.debug('too new! rejecting all occurences')
                for ep in eps:
                    feed.reject(self.parser2entry[ep], 'too much in the future from latest downloaded episode S%02dE%02d' % (latest['season'], latest['episode']))
                return True

    def process_timeframe(self, feed, config, eps, series_name):
        """
            The nasty timeframe logic, too complex even to explain (for now).
            Returns True when there's no sense trying any other logic.
        """

        if 'max_quality' in config:
            log.warning('Timeframe does not support max_quality (yet)')
        if 'min_quality' in config:
            log.warning('Timeframe does not support min_quality (yet)')
        if 'qualities' in config:
            log.warning('Timeframe does not support qualities (yet)')

        best = eps[0]

        # parse options
        amount, unit = config['timeframe'].split(' ')
        log.debug('amount: %s unit: %s' % (repr(amount), repr(unit)))
        params = {unit: int(amount)}
        try:
            timeframe = timedelta(**params)
        except TypeError:
            raise PluginWarning('Invalid time format', log)

        quality_name = config.get('quality', '720p')
        if quality_name not in qualities.registry:
            log.error('Parameter quality has unknown value: %s' % quality_name)
        quality = qualities.get(quality_name)

        # scan for quality, starting from worst quality (reverse) (old logic, see note below)
        for ep in reversed(eps):
            if quality == qualities.get(ep.quality):
                entry = self.parser2entry[ep]
                log.debug('Timeframe accepting. %s meets quality %s' % (entry['title'], quality))
                self.accept_series(feed, ep, 'quality met, timeframe unnecessary')
                return True

        # expire timeframe, accept anything
        first_seen = self.get_first_seen(feed.session, best)
        expires = first_seen + timeframe
        log.debug('timeframe: %s' % timeframe)
        log.debug('first_seen: %s' % first_seen)
        log.debug('timeframe expires: %s' % str(expires))

        stop = feed.manager.options.stop_waiting.lower() == series_name.lower()
        if expires <= datetime.now() or stop:
            entry = self.parser2entry[best]
            if stop:
                log.info('Stopped timeframe, accepting %s' % (entry['title']))
            else:
                log.info('Timeframe expired, accepting %s' % (entry['title']))
            self.accept_series(feed, best, 'expired/stopped')
            for ep in eps:
                if ep == best:
                    continue
                entry = self.parser2entry[ep]
                feed.reject(entry, 'wrong quality')
            return True
        else:
            # verbose waiting, add to backlog
            diff = expires - datetime.now()

            hours, remainder = divmod(diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            entry = self.parser2entry[best]
            log.info('Timeframe waiting %s for %sh:%smin, currently best is %s' % \
                (series_name, hours, minutes, entry['title']))

            # reject all episodes that are in timeframe
            log.debug('timeframe waiting %s episode %s, rejecting all occurrences' % (series_name, best.identifier))
            for ep in eps:
                feed.reject(self.parser2entry[ep], 'timeframe is waiting')
                # add entry to backlog (backlog is able to handle duplicate adds)
                if self.backlog:
                    # set expiring timeframe length, extending a day
                    self.backlog.add_backlog(feed, self.parser2entry[ep], '%s hours' % (hours + 24))
            return True

    # TODO: whitelist deprecated ?
    def process_qualities(self, feed, config, eps, whitelist=[]):
        """
            Accepts all wanted qualities.
            Accepts whitelisted episodes even if downloaded.
        """

        # get list of downloaded releases
        downloaded_releases = self.get_downloaded(feed.session, eps[0].name, eps[0].identifier)
        log.debug('downloaded_releases: %s' % downloaded_releases)

        accepted_qualities = []

        def is_quality_downloaded(quality):
            if quality in accepted_qualities:
                return True
            for release in downloaded_releases:
                if qualities.get(release.quality) == quality:
                    return True

        wanted_qualities = [qualities.get(name) for name in config['qualities']]
        log.debug('qualities: %s' % wanted_qualities)
        for ep in eps:
            quality = qualities.get(ep.quality)
            log.debug('ep: %s quality: %s' % (ep.data, quality))
            if quality not in wanted_qualities:
                log.debug('%s is unwanted quality' % ep.quality)
                continue
            if is_quality_downloaded(quality) and ep not in whitelist:
                feed.reject(self.parser2entry[ep], 'quality downloaded')
            else:
                feed.accept(self.parser2entry[ep], 'quality wanted')
                accepted_qualities.append(quality) # don't accept more of these

    # TODO: get rid of, see how feed.reject is called, consistency!
    def accept_series(self, feed, parser, reason):
        """Accept this series with a given reason"""
        entry = self.parser2entry[parser]
        if parser.field:
            if entry[parser.field] != parser.data:
                log.critical('BUG? accepted title is different from parser.data %s != %s, field=%s, series=%s' % \
                    (entry[parser.field], parser.data, parser.field, parser.name))
        feed.accept(entry, reason)

    def on_feed_exit(self, feed):
        """Learn succeeded episodes"""
        log.debug('on_feed_exit')
        for entry in feed.accepted:
            if 'series_release' in entry:
                log.debug('marking %s as downloaded' % entry['series_release'])
                entry['series_release'].downloaded = True
            else:
                log.debug('%s is not a series' % entry['title'])

#
# Register plugins
#

register_plugin(FilterSeries, 'series')
register_plugin(SeriesReport, '--series', builtin=True)
register_plugin(SeriesForget, '--series-forget', builtin=True)

register_parser_option('--series', action='callback', callback=SeriesReport.optik_series,
                       help='Display series summary.')

register_parser_option('--series-forget', action='callback', callback=SeriesForget.optik_series_forget,
                       help='Remove complete series or single episode from database: <NAME> [EPISODE]')

register_parser_option('--stop-waiting', action='store', dest='stop_waiting', default='',
                       metavar='NAME', help='Stop timeframe for a given series.')
