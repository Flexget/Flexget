import logging
import re
import string
from datetime import tzinfo, timedelta, datetime
from feed import Entry
from sys import maxint
from manager import ModuleWarning
from utils.serieparser import SerieParser

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('series')

class FilterSeries:

    """
        Intelligent filter for tv-series. This solves duplicate downloads
        problem that occurs when using patterns (regexp) matching since same
        episode is often released by multiple groups.

        Example configuration:

        series:
          - some series
          - another series
          
        If "some serie" and "another serie" have understandable episode
        numbering any given episode is downloaded only once.

        So if we get same episode twice:
        
        Some.Series.S2E10.More.Text
        Some.Series.S2E10.Something.Else

        Only first file is downloaded.

        If different qualities come available at the same moment,
        flexget will always download the best one (up to 720p by default).

        Supports default settings trough settings block in configuration file.

        Advanced usage with regexps:
        ----------------------------

        The standard name matching is not perfect, if you're used to working with regexps you can
        specify regexp that is used to test if entry is a defined series.

        You can also give regexps to episode number matching or unique id matching if it doesn't have
        normal episode numbering scheme (season, episode).

        Example:

        series:
          - some serie:
              name_patterns: ^some.serie
              ep_patterns: (\d\d)-(\d\d\d)  # must return TWO groups
              id_patterns: (\d\d\d)         # can return any number of groups
        
        Timeframe:
        ----------

        Series filter allows you to specify a timeframe for each series in which
        flexget waits better quality.

        Example configuration:

        series:
          - some series:
              timeframe:
                hours: 4
                enough: 720p
          - another series
          - third series

        In this example when a epsisode of 'some serie' appears, flexget will wait
        for 4 hours in case and then proceeds to download best quality available.

        The enough parameter will tell the quality that you find good enough to start
        downloading without waiting whole timeframe. If qualities meeting enough parameter
        and above are available, flexget will prefer the enough. Ie. if enough value is set
        to 'hdtv' and qualities dsk, hdtv and 720p are available, hdtv will be chosen.
        If we take hdtv off from list, 720p would be downloaded.

        Enough has default value of 720p.

        Possible values for enough (in order): 1080p, 1080, 720p, 720, hr, dvd, hdtv, dsr, dsrip

        Custom path:
        ------------

        Specify download path for series.

        Example:

        series:
          - some series:
              path: ~/download/some_series/
          - another series
          - third series

        Example with timeframe:

        series:
          - some series:
              timeframe:
                hours: 4
              path: ~/download/some_series/
          - another series
          - third series

        Watched:
        --------

        If you already watched some episodes when adding a new series, you can specify a
        season/episode number of the last episode you know.

        Example:

        series:
            - some series:
                watched:
                    season: 2
                    episode: 3
            - another series
            - third series

        This example would reject everything prior to episode 4 of season 2.

        The parameter episode is optional, if it is missing, the entire first and second
        season would be skipped.
    """

    def register(self, manager, parser):
        manager.register('series')
        parser.add_option('--stop-waiting', action='store', dest='stop_waiting', default=False,
                          help='Stop timeframe for a given series.')

    def validator(self):
        """Validate configuration format for this module"""
        import validator
        log.warning('TODO: fix series module validator')
        return validator.factory('any')
        
        """
        from validator import ListValidator
        series = ListValidator()
        # just plain names
        series.accept(str)
        series.accept(int)
        # or "bundles" with serie name as key ..
        bundle = series.accept(dict)
        # prevent invalid indentation level
        bundle.reject_keys(['path', 'timeframe', 'name_patterns', 'ep_patterns', 'id_patterns', 'watched'])
        # accept serie name, which can be anything ...
        options = bundle.accept_any_key(dict)
        options.accept('path', str)
        # these patterns can be given in as a single string ..
        options.accept('name_patterns', str)
        options.accept('ep_patterns', str)
        options.accept('id_patterns', str)
        # .. or as list containing strings
        options.accept('name_patterns', list).accept(str)
        options.accept('ep_patterns', list).accept(str)
        options.accept('id_patterns', list).accept(str)
        # timeframe dict
        timeframe = options.accept('timeframe', dict)
        timeframe.accept('hours', int)
        timeframe.accept('enough', SerieParser.qualities)
        watched = options.accept('watched', dict)
        watched.accept('season', int)
        watched.accept('episode', int)
        series.validate(config)
        return series.errors.messages
        """

    def feed_input(self, feed):
        """Retrieve stored series from cache, in case they've been expired from feed while waiting"""
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

    def cmp_serie_quality(self, s1, s2):
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

            series = {} # ie. S1E2: [Serie Instance, Serie Instance, ..]
            for entry in feed.entries:
                for field, data in entry.iteritems():
                    # skip non string values and empty strings
                    if not isinstance(data, basestring): continue
                    if not data: continue
                    # TODO: improve, use only single instance to test?
                    serie = SerieParser()
                    serie.name = str(name)
                    serie.data = data
                    serie.ep_regexps = ep_patterns + serie.ep_regexps
                    serie.id_regexps = id_patterns + serie.id_regexps
                    # do not use builtin list for id when ep configured and vice versa
                    if conf.has_key('ep_patterns') and not conf.has_key('id_patterns'):
                        serie.id_regexps = []
                    if conf.has_key('id_patterns') and not conf.has_key('ep_patterns'):
                        serie.ep_regexps = []
                    serie.name_regexps.extend(name_patterns)
                    serie.parse()
                    # serie is not valid if it does not match given name / regexp or fails with exception
                    if serie.valid:
                        break
                else:
                    continue

                # set custom download path
                if conf.has_key('path'):
                    log.debug('setting %s custom path to %s' % (entry['title'], conf.get('path')))
                    entry['path'] = conf.get('path')
                serie.entry = entry
                self.store(feed, serie, entry)
                # add this episode into list of available episodes
                eps = series.setdefault(serie.identifier(), [])
                eps.append(serie)

            # choose episode from available qualities
            for identifier, eps in series.iteritems():
                if not eps: continue
                eps.sort(self.cmp_serie_quality)
                best = eps[0]
                
                # episode (with this id) has been downloaded
                if self.downloaded(feed, best):
                    log.debug('Series %s episode %s is already downloaded, rejecting all occurences' % (name, identifier))
                    for ep in eps:
                        feed.reject(ep.entry)
                    continue

                # reject episodes that have been marked as watched in config file
                if conf.has_key('watched'):
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
                    # allow few episodes "backwards" in case missing
                    grace = len(series) + 2
                    if best.season < latest['season'] or (best.season == latest['season'] and best.episode < latest['episode'] - grace):
                        log.debug('Series %s episode %s does not meet episode advancement, rejecting all occurrences' % (name, identifier))
                        for ep in eps:
                            feed.reject(ep.entry)
                        continue

                # timeframe present
                if conf.has_key('timeframe'):
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
                            self.accept_serie(feed, ep)
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
                    if (age_hours == 0 and diff.seconds < 60) and not feed.unittest:
                        log.info('Timeframe waiting %s for %s hours, currently best is %s' % (name, hours, best.entry['title']))
                    # stop timeframe
                    if age_hours >= hours or stop:
                        if stop:
                            log.info('Stopped timeframe, accepting %s' % (best.entry['title']))
                        else:
                            log.info('Timeframe expired, accepting %s' % (best.entry['title']))
                        self.accept_serie(feed, best)
                    else:
                        log.debug('Timeframe ignoring %s' % (best.entry['title']))
                else:
                    # no timeframe, just choose best
                    self.accept_serie(feed, best)

        # filter ALL entries, only previously accepted will remain
        # other modules may still accept entries
        for entry in feed.entries:
            feed.filter(entry)

    def accept_serie(self, feed, serie):
        """Helper method for accepting serie"""
        log.debug('Accepting %s' % serie.entry)
        feed.accept(serie.entry)
        # store serie instance to entry for later use
        serie.entry['serie_parser'] = serie
        # remove entry instance from serie instance, not needed any more (save memory, circular reference?)
        serie.entry = None

    def reject_eps(self, feed, eps):
        for ep in eps:
            feed.reject(ep.entry)

    def get_first_seen(self, feed, serie):
        """Return datetime when this episode of serie was first seen"""
        fs = feed.shared_cache.get(serie.name)[serie.identifier()]['info']['first_seen']
        return datetime(*fs)
        
    def get_latest_info(self, feed, serie):
        """Return latest known identifier in dict (season, episode) for serie name"""
        latest = feed.shared_cache.get(serie.name).get('latest', {})
        return {'season': latest.get('season', 0), 'episode': latest.get('episode', 0)}

    def downloaded(self, feed, serie):
        """Return true if this episode of serie is downloaded"""
        cache = feed.shared_cache.get(serie.name)
        return cache[serie.identifier()]['info']['downloaded']

    def store(self, feed, serie, entry):
        """Stores serie into cache"""
        # serie_name:
        #   S1E2:
        #     info:
        #       first_seen: <time>
        #       downloaded: <boolean>
        #     720p: <entry>
        #     dsr: <entry>
        cache = feed.shared_cache.storedefault(serie.name, {}, 30)
        latest = cache.setdefault('latest', {})
        episode = cache.setdefault(serie.identifier(), {})
        info = episode.setdefault('info', {})
        # store and make first seen time
        info.setdefault('first_seen', list(datetime.today().timetuple())[:-4])
        info.setdefault('downloaded', False)
        # save last known (episode advancement)
        if serie.season and serie.episode:
            if latest.get('episode', 0) < serie.episode and latest.get('season', 0) < serie.season:
                latest['season'] = serie.season
                latest['episode'] = serie.episode
        # copy of entry, we don't want to ues original reference ...
        ec = {}
        ec['title'] = entry['title']
        ec['url'] = entry['url']
        episode.setdefault(serie.quality, ec)

    def mark_downloaded(self, feed, serie):
        """Mark episode in persistence as being downloaded"""
        log.debug('marking %s as downloaded' % serie.identifier())
        cache = feed.shared_cache.get(serie.name)
        cache[serie.identifier()]['info']['downloaded'] = True

    def feed_exit(self, feed):
        """Learn succeeded episodes"""
        for entry in feed.entries:
            serie = entry.get('serie_parser')
            if serie:
                self.mark_downloaded(feed, serie)