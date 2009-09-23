import logging
from datetime import datetime, timedelta
from flexget.utils.series import SeriesParser

from flexget.manager import Base
from flexget.plugin import *
from sqlalchemy import Column, Integer, String, DateTime, Boolean, PickleType
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
    downloaded = Column(Boolean, default=False)
    first_seen = Column(DateTime, default=datetime.now())
    
    season = Column(Integer)
    number = Column(Integer)

    series_id = Column(Integer, ForeignKey('series.id'))
    qualities = relation('Quality', backref='episode')

    def __repr__(self):
        return '<Episode(identifier=%s)>' % (self.identifier)

class Quality(Base):

    __tablename__ = 'episode_qualities'

    id = Column(Integer, primary_key=True)
    quality = Column(String)
    entry = Column(PickleType)
    episode_id = Column(Integer, ForeignKey('series_episodes.id'))

    def __repr__(self):
        return '<Quality(quality=%s)>' % (self.quality)

class FilterSeries:

    """
        Intelligent filter for tv-series.
        
        http://flexget.com/wiki/FilterSeries
    """
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
            advanced.accept('text', key='quality') # TODO: allow only SeriesParser.qualities
            advanced.accept('text', key='timeframe')
            # watched
            watched = advanced.accept('dict', key='watched')
            watched.accept('number', key='season')
            watched.accept('number', key='episode')

        def build_list(series):
            """Build series list to series."""
            series.accept('text')
            bundle = series.accept('dict')
            # prevent invalid indentation level
            bundle.reject_keys(['set', 'path', 'timeframe', 'name_regexp', 'ep_regexp', 'id_regexp', 'watched'])
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
        settings_group = settings.accept_any_key('dict')
        build_options(settings_group)

        group = advanced.accept_any_key('list')        
        build_list(group)

        return root

    # TODO: re-implement (as new (sub)-plugin InputBacklog ?)
    """
    def feed_input(self, feed):
        # Retrieve stored series from cache, in case they've been expired from feed while waiting
        for name in feed.config.get('series', []):
            if isinstance(name, dict):
                name = name.items()[0][0]
            serie = feed.shared_cache.get(name)
            if not serie: continue
            for identifier in serie.keys():
                # don't add downloaded episodes
                if serie[identifier].get('info', {}).get('downloaded', False):
                    continue
                # add all qualities
                for quality in SeriesParser.qualities:
                    if quality == 'info': continue # a hack, info dict is not quality
                    entry = serie[identifier].get(quality)
                    if not entry: continue
                    # check if this episode is still in feed, if not then add it
                    exists = False
                    for feed_entry in feed.entries:
                        if feed_entry['title'] == entry['title'] and feed_entry['url'] == entry['url']:
                            exists = True
                    if not exists:
                        log.debug('restoring entry %s from cache' % entry['title'])
                        # TODO: temp fix, do better
                        e = Entry()
                        e['title'] = entry['title']
                        e['url'] = entry['url']
                        feed.entries.append(e)
    """

    def generate_config(self, feed):
        """Generate advanced form configuration dictionary from feed configuration. This way we do not
        need to handle different configuration forms in the logic."""

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
            
        return config

    def feed_filter(self, feed):
        """Filter series"""
        
        config = self.generate_config(feed)
        for group_name, group_series in config.iteritems():
            # TODO: do we even need settings block in the config at this point?
            if group_name == 'settings':
                continue
            for series_item in group_series:
                series_name, series_config = series_item.items()[0]
                log.log(5, 'series_name: %s series_config: %s' % (series_name, series_config))
                series = self.parse_series(feed, series_name, series_config)
                self.process_series(feed, series, series_name, series_config)

    def parse_series(self, feed, series_name, config):
        """Search for series_name and return dict containing all episodes from it."""

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
            
        # key: series (episode) identifier ie. S1E2
        # value: seriesparser
        series = {}
        for entry in feed.entries:
            for field, data in sorted(entry.items(), cmp=field_order):
                # skip non string values and empty strings
                if not isinstance(data, basestring) or not data: 
                    continue
                parser = SeriesParser()
                parser.name = series_name
                parser.data = data
                parser.ep_regexps = get_as_array(config, 'ep_regexp') + parser.ep_regexps
                parser.id_regexps = get_as_array(config, 'id_regexp') + parser.id_regexps
                # do not use builtin list for id when ep configigured and vice versa
                if 'ep_regexp' in config and not 'id_regexp' in config:
                    parser.id_regexps = []
                if 'id_regexp' in config and not 'ep_regexp' in config:
                    parser.ep_regexps = []
                parser.name_regexps.extend(get_as_array(config, 'name_regexp'))
                parser.parse()
                # series is not valid if it does not match given name / regexp or fails with exception
                if parser.valid:
                    log.debug('Detected quality: %s from: %s' % (parser.quality, field))
                    break
            else:
                continue
            
            # add series, season and episode to entry
            entry['series_name'] = series_name
            entry['series_season'] = parser.season
            entry['series_episode'] = parser.episode
            entry['series_id'] = parser.id
            
            # set custom download path TODO: Remove, replaced by set?
            if 'path' in config:
                log.debug('setting %s custom path to %s' % (entry['title'], config.get('path')))
                entry['path'] = config.get('path')
            
            # accept info from set: and place into the entry
            if 'set' in config:
                set = get_plugin_by_name('set')
                set.instance.modify(entry, config.get('set'))
                
            parser.entry = entry
            # add this episode into list of available episodes
            eps = series.setdefault(parser.identifier(), [])
            eps.append(parser)
            # store this episode into database
            self.store(feed, parser)
            
        return series

    def process_series(self, feed, series, series_name, config):
        """Accept or Reject episode from available qualities, or postpone choosing."""
        for identifier, eps in series.iteritems():
            if not eps: continue
            eps.sort(lambda x,y: cmp(x.quality, y.quality))
            best = eps[0]
            
            # episode (with this id) has been downloaded
            if self.downloaded(feed, best):
                log.debug('Series %s episode %s is already downloaded, rejecting all occurences' % (series_name, identifier))
                for ep in eps:
                    feed.reject(ep.entry, 'already downloaded')
                continue

            # reject episodes that have been marked as watched in configig file
            if 'watched' in config:
                from sys import maxint
                wconfig = config.get('watched')
                season = wconfig.get('season', -1)
                episode = wconfig.get('episode', maxint)
                if best.season < season or (best.season == season and best.episode <= episode):
                    log.debug('%s episode %s is already watched, rejecting all occurrences' % (series_name, identifier))
                    for ep in eps:
                        feed.reject(ep.entry, 'watched')
                    continue
                    
            # episode advancement, only when using season, ep identifier
            if best.season and best.episode:
                latest = self.get_latest_info(feed, best)
                if latest:
                    # allow few episodes "backwards" in case of missed eps
                    grace = len(series) + 2
                    if best.season < latest['season'] or (best.season == latest['season'] and best.episode < latest['episode'] - grace):
                        log.debug('%s episode %s does not meet episode advancement, rejecting all occurrences' % (series_name, identifier))
                        for ep in eps:
                            feed.reject(ep.entry, 'episode advancement')
                        continue
                else:
                    log.debug('No latest info available')
                    
            # plain quality
            if 'quality' in config and not 'timeframe' in config:
                for ep in eps:
                    if ep.quality == config['quality']:
                        self.accept_series(feed, ep, 'meets quality')
                    else:
                        feed.reject(ep.entry, 'quality') # is this needed or a good idea?
                continue

            # timeframe present
            if 'timeframe' in config:
                
                # parse options
                amount, unit = config['timeframe'].split(' ')
                log.debug('amount: %s unit: %s' % (repr(amount), repr(unit)))
                params = {unit:int(amount)}
                try:
                    timeframe = timedelta(**params)
                except TypeError:
                    raise PluginWarning('Invalid time format', log)
                quality = config.get('quality', '720p')
                if not quality in SeriesParser.qualities:
                    log.error('Parameter quality has unknown value: %s' % quality)
                stop = feed.manager.options.stop_waiting == series_name

                # scan for quality, starting from worst quality (reverse) (old logic, see note below)
                eps.reverse()

                def cmp_quality(q1, q2):
                    return cmp(SeriesParser.qualities.index(q1), SeriesParser.qualities.index(q2))

                # scan for episode that meets defined quality
                found_quality = False
                for ep in eps:
                    # Note: switch == operator to >= if wish to enable old behaviour
                    if cmp_quality(quality, ep.quality) == 0: # 1=greater, 0=equal, -1=does not meet
                        log.debug('Timeframe accepting. %s meets quality %s' % (ep.entry['title'], quality))
                        self.accept_series(feed, ep, 'quality met, timeframe unnecessary')
                        found_quality = True
                        break
                if found_quality:
                    continue
                        
                # expire timeframe, accept anything
                diff = datetime.now() - self.get_first_seen(feed, best)
                if (diff.seconds < 60) and not feed.manager.unit_test:
                    log.info('Timeframe waiting %s for %s hours, currently best is %s' % (series_name, timeframe.seconds/60**2, best.entry['title']))
                
                first_seen = self.get_first_seen(feed, best)
                log.debug('timeframe: %s' % timeframe)
                log.debug('first_seen: %s' % first_seen)
                log.debug('first_seen + timeframe: %s' % str(first_seen + timeframe))
                
                if first_seen + timeframe <= datetime.now() or stop:
                    if stop:
                        log.info('Stopped timeframe, accepting %s' % (best.entry['title']))
                    else:
                        log.info('Timeframe expired, accepting %s' % (best.entry['title']))
                    self.accept_series(feed, best, 'expired/stopped')
                    for ep in eps:
                        if ep == best:
                            continue
                        feed.reject(ep.entry, 'wrong quality')
                    continue
                else:
                    log.debug('timeframe waiting %s episode %s, rejecting all occurrences' % (series_name, identifier))
                    for ep in eps:
                        feed.reject(ep.entry, 'timeframe waiting')
                    continue

            # no special configuration, just choose the best
            self.accept_series(feed, best, 'choose best')

    def accept_series(self, feed, parser, reason):
        """Helper method for accepting series"""
        log.debug('Accepting %s because %s' % (parser.entry, reason))
        feed.accept(parser.entry, reason)
        # store series parser instance to entry for later use
        parser.entry['series_parser'] = parser
        # remove entry instance from parser, not needed any more (prevents circular reference?)
        parser.entry = None

    def get_first_seen(self, feed, parser):
        """Return datetime when this episode of series was first seen"""
        episode = feed.session.query(Episode).select_from(join(Episode, Series)).\
            filter(Series.name==parser.name).filter(Episode.identifier==parser.identifier()).first()
        return episode.first_seen
        
    def get_latest_info(self, feed, parser):
        """Return latest known identifier in dict (season, episode) for series name"""
        episode = feed.session.query(Episode).select_from(join(Episode, Series)).\
            filter(Series.name==parser.name).order_by(Episode.number).order_by(Episode.season).first()
        if not episode:
            return False
        log.debug('get_latest_info, series: %s season: %s episode: %s' % \
                  (parser.name, episode.season, episode.number))
        return {'season':episode.season, 'episode':episode.number}

    def downloaded(self, feed, parser):
        """Return true if episode is downloaded"""
        episode = feed.session.query(Episode).select_from(join(Episode, Series)).\
            filter(Series.name==parser.name).filter(Episode.identifier==parser.identifier()).first()
        if episode:
            return episode.downloaded
        return False

    def store(self, feed, parser):
        """Push series information into database"""
        # if does not exist in database, add new
        series = feed.session.query(Series).filter(Series.name==parser.name).first()
        if not series:
            log.debug('add series %s into database' % parser.name)
            series = Series()
            series.name = parser.name
            feed.session.add(series)
        
        # if episode does not exist in series, add new
        episode = feed.session.query(Episode).filter(Episode.series_id==series.id).\
            filter(Episode.identifier==parser.identifier()).first()
        if not episode:
            log.debug('add episode %s into series %s' % (parser.identifier(), parser.name))
            episode = Episode()
            episode.identifier = parser.identifier()
            # if episodic format
            if parser.season and parser.episode:
                episode.season = parser.season
                episode.number = parser.episode
            series.episodes.append(episode) # pylint: disable-msg=E1103

        # if quality does not exists in episodes, add new
        quality = feed.session.query(Quality).filter(Quality.episode_id==episode.id).\
            filter(Quality.quality==parser.quality).first()
        if not quality:
            log.debug('add quality %s into series %s episode %s' % (parser.quality, \
                                                                    parser.name, parser.identifier()))
            quality = Quality()
            
            # TODO:
            # This CRASHES sqlalchemy in SOME cases, not all
            #quality.entry = parser.entry
            
            # HACK: create copy of entry, this however does NOT contain all information from the original!
            from flexget.feed import Entry
            quality.entry = Entry(parser.entry['title'], parser.entry['url'])

            quality.quality = parser.quality
            episode.qualities.append(quality) # pylint: disable-msg=E1103

    def mark_downloaded(self, feed, parser):
        """Mark episode as being downloaded"""
        log.debug('marking as downloaded %s' % parser)
        episode = feed.session.query(Episode).select_from(join(Episode, Series)).\
            filter(Series.name==parser.name).filter(Episode.identifier==parser.identifier()).first()
        episode.downloaded = True

    def feed_exit(self, feed):
        """Learn succeeded episodes"""
        for entry in feed.accepted:
            parser = entry.get('series_parser')
            if parser:
                self.mark_downloaded(feed, parser)

register_plugin(FilterSeries, 'series')
register_parser_option('--stop-waiting', action='store', dest='stop_waiting',
                       default=False, help='Stop timeframe for a given series.')
