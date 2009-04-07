import logging
import re
from datetime import tzinfo, timedelta, datetime
from feed import Entry
from sys import maxint
from manager import ModuleWarning
from utils.serieparser import SerieParser

from manager import Session, Base
from sqlalchemy import Column, Integer, String, Unicode, DateTime, Boolean, PickleType, func
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation

log = logging.getLogger('series')

class Series(Base):
    
    __tablename__ = 'series'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    episodes = relation('Episode', backref='series')

    def __str__(self):
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

    def __init__(self):
        #self.first_seen = datetime.now()
        #self.downloaded = False
        pass

    def __str__(self):
        return '<Episode(identifier=%s)>' % (self.identifier)


class Quality(Base):

    __tablename__ = 'episode_qualities'

    id = Column(Integer, primary_key=True)
    quality = Column(String)
    entry = Column(PickleType)
    episode_id = Column(Integer, ForeignKey('series_episodes.id'))

    def __str__(self):
        return '<Quality(quality=%s)>' % (self.quality)

class FilterSeries:

    """
        Intelligent filter for tv-series.
        
        http://flexget.com/wiki/FilterSeries
    """

    def register(self, manager, parser):
        manager.register('series')
        parser.add_option('--stop-waiting', action='store', dest='stop_waiting', default=False,
                          help='Stop timeframe for a given series.')

    def validator(self):
        import validator
        series = validator.factory('list')
        series.accept('text')
        series.accept('number')
        bundle = series.accept('dict')
        # prevent invalid indentation level
        bundle.reject_keys(['path', 'timeframe', 'name_patterns', 'ep_patterns', 'id_patterns', 'watched'])
        advanced = bundle.accept_any_key('dict')
        advanced.accept('text', key='path')
        # regexes can be given in as a single string ..
        advanced.accept('text', key='name_patterns')
        advanced.accept('text', key='ep_patterns')
        advanced.accept('text', key='id_patterns')
        # .. or as list containing strings
        advanced.accept('list', key='name_patterns').accept('text')
        advanced.accept('list', key='ep_patterns').accept('text')
        advanced.accept('list', key='id_patterns').accept('text')
        # timeframe dict
        timeframe = advanced.accept('dict', key='timeframe')
        timeframe.accept('number', key='hours')
        timeframe.accept('text', key='enough') # TODO: allow only SerieParser.qualities
        # watched
        watched = advanced.accept('dict', key='watched')
        watched.accept('number', key='season')
        watched.accept('number', key='episode')
        return series

    # TODO: re-implement!
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
                for quality in SerieParser.qualities:
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

    def cmp_series_quality(self, s1, s2):
        return self.cmp_quality(s1.quality, s2.quality)

    def cmp_quality(self, q1, q2):
        return cmp(SerieParser.qualities.index(q1), SerieParser.qualities.index(q2))

    def feed_filter(self, feed):
        """Filter series"""
        for name in feed.config.get('series', []):
            # start with default settings
            conf = feed.manager.get_settings('series', {})
            if isinstance(name, dict):
                name, conf = name.items()[0]
                if conf is None:
                    log.critical('Series %s has unexpected \':\'' % name)
                    continue
                # merge with default settings
                conf = feed.manager.get_settings('series', conf)

            def get_as_array(conf, key):
                v = conf.get(key, [])
                if isinstance(v, basestring):
                    return [v]
                return v

            ep_patterns = get_as_array(conf, 'ep_patterns')
            id_patterns = get_as_array(conf, 'id_patterns')
            name_patterns = get_as_array(conf, 'name_patterns')

            series = {} # ie. S1E2: [Parser, Parser*n]
            for entry in feed.entries:
                for _, data in entry.iteritems():
                    # skip non string values and empty strings
                    if not isinstance(data, basestring): continue
                    if not data: continue
                    parser = SerieParser()
                    parser.name = str(name)
                    parser.data = data
                    parser.ep_regexps = ep_patterns + parser.ep_regexps
                    parser.id_regexps = id_patterns + parser.id_regexps
                    # do not use builtin list for id when ep configured and vice versa
                    if 'ep_patterns' in conf and not 'id_patterns' in conf:
                        parser.id_regexps = []
                    if 'id_patterns' in conf and not 'ep_patterns' in conf:
                        parser.ep_regexps = []
                    parser.name_regexps.extend(name_patterns)
                    parser.parse()
                    # series is not valid if it does not match given name / regexp or fails with exception
                    if parser.valid:
                        break
                else:
                    continue

                # set custom download path
                if 'path' in conf:
                    log.debug('setting %s custom path to %s' % (entry['title'], conf.get('path')))
                    entry['path'] = conf.get('path')
                parser.entry = entry
                self.store(feed, parser)
                # add this episode into list of available episodes
                eps = series.setdefault(parser.identifier(), [])
                eps.append(parser)

            # choose episode from available qualities
            for identifier, eps in series.iteritems():
                if not eps: continue
                eps.sort(self.cmp_series_quality)
                best = eps[0]
                
                # episode (with this id) has been downloaded
                if self.downloaded(feed, best):
                    log.debug('Series %s episode %s is already downloaded, rejecting all occurences' % (name, identifier))
                    for ep in eps:
                        feed.reject(ep.entry)
                    continue

                # reject episodes that have been marked as watched in config file
                if 'watched' in conf:
                    wconf = conf.get('watched')
                    season = wconf.get('season', -1)
                    episode = wconf.get('episode', maxint)
                    if best.season < season or (best.season == season and best.episode <= episode):
                        log.debug('Series %s episode %s is already watched, rejecting all occurrences' % (name, identifier))
                        for ep in eps:
                            feed.reject(ep.entry)
                        continue
                        
                # episode advancement, only when using season, ep identifier
                if best.season and best.episode:
                    latest = self.get_latest_info(feed, best)
                    if latest:
                        # allow few episodes "backwards" in case missing
                        grace = len(series) + 2
                        if best.season < latest['season'] or (best.season == latest['season'] and best.episode < latest['episode'] - grace):
                            log.debug('Series %s episode %s does not meet episode advancement, rejecting all occurrences' % (name, identifier))
                            for ep in eps:
                                feed.reject(ep.entry)
                            continue
                    else:
                        log.debug('No latest info available')

                # timeframe present
                if 'timeframe' in conf:
                    tconf = conf.get('timeframe')
                    hours = tconf.get('hours', 0)
                    enough = tconf.get('enough', '720p')
                    stop = feed.manager.options.stop_waiting == name

                    if not enough in SerieParser.qualities:
                        log.error('Parameter enough has unknown value: %s' % enough)

                    # scan for enough, starting from worst quality (reverse)
                    eps.reverse()
                    found_enough = False
                    for ep in eps:
                        if self.cmp_quality(enough, ep.quality) >= 0: # 1=greater, 0=equal, -1=does not meet
                            log.debug('Timeframe accepting. %s meets quality %s' % (ep.entry['title'], enough))
                            self.accept_series(feed, ep)
                            found_enough = True
                            break
                    if found_enough:
                        continue
                            
                    # timeframe
                    diff = datetime.today() - self.get_first_seen(feed, best)
                    age_hours = divmod(diff.days*24*60*60 + diff.seconds, 60*60)[0]
                    log.debug('Age hours: %i, seconds: %i - %s ' % (age_hours, diff.seconds, best))
                    log.debug('Best ep in %i hours is %s' % (hours, best))
                    # log when it is added to timeframe wait list (a bit hacky way to detect first time, by age)
                    if (age_hours == 0 and diff.seconds < 60) and not feed.manager.unit_test:
                        log.info('Timeframe waiting %s for %s hours, currently best is %s' % (name, hours, best.entry['title']))
                    # stop timeframe
                    if age_hours >= hours or stop:
                        if stop:
                            log.info('Stopped timeframe, accepting %s' % (best.entry['title']))
                        else:
                            log.info('Timeframe expired, accepting %s' % (best.entry['title']))
                        self.accept_series(feed, best)
                    else:
                        log.debug('Timeframe ignoring %s' % (best.entry['title']))
                else:
                    # no timeframe, just choose best
                    self.accept_series(feed, best)

        # filter ALL entries, only previously accepted will remain
        # other modules may still accept entries
        for entry in feed.entries:
            feed.filter(entry)

    def accept_series(self, feed, parser):
        """Helper method for accepting series"""
        log.debug('Accepting %s' % parser.entry)
        feed.accept(parser.entry)
        # store serie instance to entry for later use
        parser.entry['series_parser'] = parser
        # remove entry instance from serie instance, not needed any more (save memory, circular reference?)
        parser.entry = None

    def get_first_seen(self, feed, parser):
        """Return datetime when this episode of serie was first seen"""
        session = Session()
        episode = session.query(Episode).filter(Series.name==parser.name).filter(Episode.series_id==Series.id).first()
        session.close()
        return episode.first_seen
        
    def get_latest_info(self, feed, parser):
        """Return latest known identifier in dict (season, episode) for series name"""
        session = Session()
        # TODO: this could be done using single query, but how?
        series = session.query(Series).filter(Series.name==parser.name).first()
        log.debug('get_latest_info found series')
        if not series:
            session.close()
            return False
        episode = session.query(Episode).filter(func.max(Episode.season)).\
            filter(func.max(Episode.number)).filter(Episode.series_id==series.id).first()
        session.close()
        return (episode.season, episode.number)

    def downloaded(self, feed, series):
        """Return true if this episode of series is downloaded"""
        """
        cache = feed.shared_cache.get(serie.name)
        return cache[serie.identifier()]['info']['downloaded']
        """
        return False

    def store(self, feed, parser):
        """Push series parser information into database"""
        session = Session()
        
        # if does not exist in database, add new
        series = session.query(Series).filter(Series.name==parser.name).first()
        if not series:
            log.debug('Adding series %s into database' % parser.name)
            series = Series()
            series.name = parser.name
            session.add(series)
        
        # if episode does not exist in series, add new
        episode = session.query(Episode).filter(Episode.series_id==series.id).\
            filter(Episode.identifier==parser.identifier).first()
        if not episode:
            log.debug('Adding episode %s into series %s' % (parser.identifier(), parser.name))
            episode = Episode()
            episode.identifier = parser.identifier()
            # if episodic format
            if parser.season and parser.episode:
                episode.season = parser.season
                episode.number = parser.episode
            series.episodes.append(episode) # pylint: disable-msg=E1103

        # if quality does not exists in episodes, add new
        quality = session.query(Quality).filter(Quality.episode_id==episode.id).\
            filter(Quality.quality==parser.quality).first()
        if not quality:
            log.debug('Adding quality %s into series %s episode %s' % (parser.quality, parser.name, parser.identifier()))
            quality = Quality()
            quality.entry = parser.entry
            quality.quality = parser.quality
            episode.qualities.append(quality) # pylint: disable-msg=E1103
        
        session.commit()

    def mark_downloaded(self, feed, parser):
        """Mark episode as being downloaded"""
        
        log.debug('marking series %s identifier %s as downloaded' % (parser.name, parser.identifier()))

        session = Session()
        # TODO: this could be done using single query, but how?
        series = session.query(Series).filter(Series.name==parser.name).one()
        episode = session.query(Episode).filter(Episode.series_id==series.id).\
            filter(Episode.identifier==parser.identifier).one()
        episode.downloaded = True
        session.commit()

    def feed_exit(self, feed):
        """Learn succeeded episodes"""
        for entry in feed.entries:
            parser = entry.get('series_parser')
            if parser:
                self.mark_downloaded(feed, parser)