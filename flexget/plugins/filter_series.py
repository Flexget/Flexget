import logging
from datetime import datetime, timedelta
from flexget.utils.titles import SeriesParser, ParseWarning
from flexget.manager import Base
from flexget.plugin import *
from sqlalchemy import Column, Integer, String, DateTime, Boolean, desc
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation, join

log = logging.getLogger('series')


class Series(Base):

    __tablename__ = 'series'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    episodes = relation('Episode', backref='series')

    def __repr__(self):
        return '<Series(name=%s)>' % (self.name)


class Episode(Base):

    __tablename__ = 'series_episodes'

    id = Column(Integer, primary_key=True)
    identifier = Column(String)
    first_seen = Column(DateTime, default=datetime.now())

    season = Column(Integer)
    number = Column(Integer)

    series_id = Column(Integer, ForeignKey('series.id'))
    releases = relation('Release', backref='episode')

    def __repr__(self):
        return '<Episode(identifier=%s)>' % (self.identifier)


class Release(Base):

    __tablename__ = 'episode_releases'

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey('series_episodes.id'))
    quality = Column(String)
    downloaded = Column(Boolean, default=False)
    proper = Column(Boolean, default=False)
    title = Column(String)

    def __repr__(self):
        return '<Release(quality=%s,downloaded=%s,proper=%s,title=%s)>' % (self.quality, self.downloaded, self.proper, self.title)


class SeriesPlugin(object):

    """Database helpers"""

    def get_first_seen(self, session, parser):
        """Return datetime when this episode of series was first seen"""
        episode = session.query(Episode).select_from(join(Episode, Series)).\
            filter(Series.name == parser.name.lower()).filter(Episode.identifier == parser.identifier).first()
        return episode.first_seen

    # TODO: profiled to be a bottleneck! ~9seconds & 2000+ calls ?
    def get_latest_info(self, session, name):
        """Return latest known identifier in dict (season, episode) for series name"""
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

        name = self.options['name'].lower()
        series = session.query(Series).filter(Series.name == name.lower()).first()
        if not series:
            print 'Unknown series %s' % name
            return

        print ' %-30s%-20s' % ('Identifier', 'Status')
        print '-' * 79

        for episode in series.episodes:
            status = ''
            for release in episode.releases:
                if release.downloaded:
                    status += '*'
                status += release.quality
                if release.proper:
                    status += '-Proper'
                status += ' '
            print ' %-30s%-20s' % (episode.identifier, status)

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
                    latest = '%s (uid)' % episode.identifier
                else:
                    latest = 's%se%s' % (str(episode.season).zfill(2), str(episode.number).zfill(2))

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

            print ' %-30s%-20s%-21s' % (series.name, latest, status)

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

            name = self.options.get('name')

            from flexget.manager import Session
            session = Session()

            if self.options.get('episode'):
                # remove by id
                identifier = self.options.get('episode').upper()
                if identifier and name:
                    series = session.query(Series).filter(Series.name == name.lower()).first()
                    if series:
                        episode = session.query(Episode).filter(Episode.identifier == identifier).first()
                        if episode:
                            print 'Removed %s %s' % (name.capitalize(), identifier)
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

        def build_options(advanced):
            advanced.accept('text', key='path')
            bundle = advanced.accept('dict', key='set')
            bundle.accept_any_key('any')
            # regexes can be given in as a single string ..
            advanced.accept('regexp', key='name_regexp')
            advanced.accept('regexp', key='ep_regexp')
            advanced.accept('regexp', key='id_regexp')
            # .. or as list containing strings
            advanced.accept('list', key='name_regexp').accept('regexp')
            advanced.accept('list', key='ep_regexp').accept('regexp')
            advanced.accept('list', key='id_regexp').accept('regexp')
            # quality
            advanced.accept('text', key='quality')                    # TODO: allow only SeriesParser.qualities
            advanced.accept('list', key='qualities').accept('text')   # TODO: ^^
            advanced.accept('text', key='min_quality')                # TODO: ^^
            advanced.accept('text', key='max_quality')                # TODO: ^^
            advanced.accept('regexp_match', key='timeframe').accept('\d+ (minutes|hours|days|weeks)')
            # strict naming
            advanced.accept('boolean', key='exact')
            # watched
            watched = advanced.accept('dict', key='watched')
            watched.accept('number', key='season')
            watched.accept('number', key='episode')

        def build_list(series):
            """Build series list to series."""
            series.accept('text')
            bundle = series.accept('dict')
            # prevent invalid indentation level
            bundle.reject_keys(['set', 'path', 'timeframe', 'name_regexp', \
                'ep_regexp', 'id_regexp', 'watched', 'quality', 'min_quality', \
                'max_quality', 'qualities', 'exact'], \
                'Option \'$key\' has invalid indentation level. It needs 2 more spaces.')
            advanced = bundle.accept_any_key('dict')
            build_options(advanced)

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
            # convert simpliest configuration internally grouped format
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
                if group_name in SeriesParser.qualities:
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
                        log.info('Auto enabling exact matching for series %s' % series_name)
                        series_config['exact'] = True

    def on_feed_filter(self, feed):
        """Filter series"""

        # TEMP: hack, test if running old database with sqlalchemy table reflection ..
        from flexget.utils.sqlalchemy_utils import table_exists
        if table_exists('episode_qualities', feed):
            log.critical('Running old database! Please see bleeding edge news!')
            feed.manager.disable_feeds()
            feed.abort()

        # TEMP: bugfix, convert all series to lowercase
        for series in feed.session.query(Series).all():
            series.name = series.name.lower()

        # add current entries into backlog memory
        if self.backlog:
            self.backlog.learn_backlog(feed, '14 days') # TODO: backlog length could be largest timeframe present

        config = self.generate_config(feed)
        self.auto_exact(config)

        for group_series in config.itervalues():
            for series_item in group_series:
                series_name, series_config = series_item.items()[0]
                log.log(5, 'series_name: %s series_config: %s' % (series_name, series_config))
                series = self.parse_series(feed, series_name, series_config)
                self.process_series(feed, series, series_name, series_config)

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

        # helper function, iterate entry fields in certain order
        def field_order(a, b):
            order = ['title', 'description']

            def index(c):
                try:
                    return order.index(c[0])
                except ValueError:
                    return 1

            return cmp(index(a), index(b))

        # key: series (episode) identifier ie. S01E02
        # value: seriesparser
        series = {}
        for entry in feed.entries:

            # determine if series is known to be in season, episode format
            # note: inside the loop for better handling multiple new eps
            # ie. after first season, episode release we stick with expect_ep
            expect_ep = False
            latest = self.get_latest_info(feed.session, series_name)
            if latest:
                if latest.get('season') and latest.get('episode'):
                    log.log(5, 'enabling expect_ep for %s' % series_name)
                    expect_ep = True

            for field, data in sorted(entry.items(), cmp=field_order):
                # skip invalid fields
                if not isinstance(data, basestring) or not data:
                    continue
                parser = SeriesParser()
                parser.name = series_name
                parser.data = data
                parser.expect_ep = expect_ep
                parser.ep_regexps = get_as_array(config, 'ep_regexp') + parser.ep_regexps
                parser.id_regexps = get_as_array(config, 'id_regexp') + parser.id_regexps
                parser.strict_name = config.get('exact', False)
                # do not use builtin list for id when ep configigured and vice versa
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
                    log.debug('%s seems to be valid %s' % (entry['title'], series_name))
                    self.parser2entry[parser] = entry
                    entry['series_parser'] = parser
                    break
            else:
                continue

            # add series, season and episode to entry
            entry['series_name'] = series_name
            entry['series_season'] = parser.season
            entry['series_episode'] = parser.episode
            # debug for #390
            try:
                entry['series_id'] = parser.identifier
            except:
                log.critical('-' * 79)
                log.critical('Found bug #390! Please report this:')
                log.critical('-' * 79)
                log.critical('series_name: %s' % series_name)
                log.critical('Entry: %s' % entry.safe_str())
                log.critical('Parser: %s' % parser)
                log.critical('-' * 79)
                continue

            # set custom download path
            if 'path' in config:
                log.debug('setting %s custom path to %s' % (entry['title'], config.get('path')))
                entry['path'] = config.get('path')

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
            eps.sort()

            log.debug('start with episodes: %s' % [e.data for e in eps])

            # reject episodes that have been marked as watched in configig file
            if 'watched' in config:
                log.debug('-' * 20 + ' watched -->')
                if self.process_watched(feed, config, eps):
                    continue

            #
            # proper handling
            #

            log.debug('-' * 20 + ' process_propers -->')
            removed, new_propers = self.process_propers(feed, eps)
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
                log.debug('-' * 20 + ' qualities -->')
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

            # Episode advancement. Used only with season based series
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
            self.accept_series(feed, best, 'choose best')

    def process_propers(self, feed, eps):
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

        accepted_qualities = []
        if 'quality' in config:
            accepted_qualities.append(config['quality'])
        else:
            qualities = SeriesParser.qualities
            min = config.get('min_quality', qualities[-1]).lower()
            max = config.get('max_quality', qualities[0]).lower()
            min_index = qualities.index(min) + 1
            max_index = qualities.index(max)
            log.debug('min: %s (%s) max: %s (%s)' % (min, min_index, max, max_index))
            for quality in qualities[max_index:min_index]:
                accepted_qualities.append(quality)
            log.debug('accepted qualities are %s' % accepted_qualities)
        # see if any of the eps match accepted qualities
        for ep in eps:
            log.log(5, 'testing %s (quality: %s) for qualities' % (ep.data, ep.quality))
            if ep.quality in accepted_qualities:
                self.accept_series(feed, ep, 'meets quality')
                break

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
        """Rjects all episodes that are too old (advancement), return True when this happens."""

        current = eps[0]
        latest = self.get_latest_info(feed.session, current.name)
        log.debug('latest: %s' % latest)
        log.debug('current: %s' % current)
        if latest:
            # allow few episodes "backwards" in case of missed eps
            grace = len(series) + 2
            if (current.season < latest['season']) or (current.season == latest['season'] and current.episode < (latest['episode'] - grace)):
                log.debug('%s episode %s does not meet episode advancement, rejecting all occurrences' % (current.name, current.identifier))
                for ep in eps:
                    feed.reject(self.parser2entry[ep], 'episode advancement')
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
        quality = config.get('quality', '720p')
        if not quality in SeriesParser.qualities:
            log.error('Parameter quality has unknown value: %s' % quality)

        # scan for quality, starting from worst quality (reverse) (old logic, see note below)
        eps.reverse()

        def cmp_quality(q1, q2):
            return cmp(SeriesParser.qualities.index(q1), SeriesParser.qualities.index(q2))

        # scan for episode that meets defined quality
        for ep in eps:
            # Note: switch == operator to >= if wish to enable old behaviour
            if cmp_quality(quality, ep.quality) == 0: # 1=greater, 0=equal, -1=does not meet
                entry = self.parser2entry[ep]
                log.debug('Timeframe accepting. %s meets quality %s' % (entry['title'], quality))
                self.accept_series(feed, ep, 'quality met, timeframe unnecessary')
                return True

        # expire timeframe, accept anything
        diff = datetime.now() - self.get_first_seen(feed.session, best)
        if (diff.seconds < 60) and not feed.manager.unit_test:
            entry = self.parser2entry[best]
            log.info('Timeframe waiting %s for %s hours, currently best is %s' % \
                (series_name, timeframe.seconds / 60 ** 2, entry['title']))

        first_seen = self.get_first_seen(feed.session, best)
        log.debug('timeframe: %s' % timeframe)
        log.debug('first_seen: %s' % first_seen)
        log.debug('timeframe expires: %s' % str(first_seen + timeframe))

        stop = feed.manager.options.stop_waiting == series_name
        if first_seen + timeframe <= datetime.now() or stop:
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
            log.debug('timeframe waiting %s episode %s, rejecting all occurrences' % (series_name, best.identifier))
            for ep in eps:
                feed.reject(self.parser2entry[ep], 'timeframe is waiting')
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

        def is_quality_downloaded(quality):
            for release in downloaded_releases:
                if release.quality == quality:
                    return True

        qualities = [quality.lower() for quality in config['qualities']]
        log.debug('qualities: %s' % qualities)
        for ep in eps:
            log.debug('qualities, quality: %s' % ep.quality)
            if not ep.quality.lower() in qualities:
                log.debug('%s is unwanted quality' % ep.quality)
                continue
            if is_quality_downloaded(ep.quality) and ep not in whitelist:
                feed.reject(self.parser2entry[ep], 'quality downloaded')
            else:
                feed.accept(self.parser2entry[ep], 'quality wanted')

    # TODO: get rid of, see how feed.reject is called, consistency!
    def accept_series(self, feed, parser, reason):
        """Accept this series with a given reason"""
        entry = self.parser2entry[parser]
        if (entry['title'] != parser.data):
            log.critical('BUG? accepted title is different from parser.data')
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
                       help='Remove complete series or single episode from database. <Series> [episode]')

register_parser_option('--stop-waiting', action='store', dest='stop_waiting', default=False,
                       metavar='NAME', help='Stop timeframe for a given series.')
