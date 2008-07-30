import logging
import re
import string
import types
from datetime import tzinfo, timedelta, datetime
from feed import Entry

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('series')

class SerieParser:
    qualities = ['1080p', '1080', '720p', '720', 'hr', 'dvd', 'dvdrip', 'hdtv', 'pdtv', 'dsr', 'dsrip', 'unknown']
    
    def __init__(self):
        # name of the serie
        self.name = None 
        # data to parse
        self.data = None 
        
        self.ep_regexps = ['s(\d+)e(\d+)', 's(\d+)ep(\d+)', '(\d+)x(\d+)']
        self.id_regexps = ['(\d\d\d\d).(\d+).(\d+)', '(\d+).(\d+).(\d\d\d\d)']
        self.name_regexps = []
        # parse produces these
        self.season = None
        self.episode = None
        self.id = None

        self.quality = 'unknown'
        # false if item does not match serie
        self.valid = False
        # optional for storing entry from which this instance is made from
        self.entry = None

    def parse(self):
        if not self.name or not self.data:
            raise Exception('SerieParser missing either name or data')
        def clean(s):
            res = s
            r = [('.', ' '), ('_', ' '),
                 ('[', ' '), (']', ' ')]
            for p in r:
                res = res.replace(*p)
            while (res.find('  ')!=-1):
                res = res.replace('  ', ' ')
            return res.lower()

        name = clean(self.name)
        data = clean(self.data)

        #log.debug('name: %s data: %s' % (name, data))
        
        name_parts = name.split(' ')
        data_parts = data.split(' ')

        # regexp name matching
        if self.name_regexps:
            name_matches = False
            # use all specified regexps to this data
            for name_re in self.name_regexps:
                m = re.search(name_re, self.data, re.IGNORECASE|re.UNICODE)
                if m:
                    name_matches = True
                    break
            if not name_matches:
                # leave this invalid
                #log.debug('FAIL: name regexps do not match')
                return
        else:
            # try to use given name old fashion way
            for part in name_parts:
                if part in data_parts:
                    data_parts.remove(part)
                else:
                    #log.debug('FAIL: part %s not found from %s' % (part, data_parts))
                    # leave this invalid
                    return

        # seach quality
        for part in data_parts:
            # search for quality
            if part in self.qualities:
                if self.qualities.index(part) < self.qualities.index(self.quality):
                    log.debug('%s storing quality %s' % (self.name, part))
                    self.quality = part
                else:
                    log.debug('%s ignoring quality %s because found better %s' % (self.name, part, self.quality))

        # search for season and episode number
        for ep_re in self.ep_regexps:
            m = re.search(ep_re, self.data, re.IGNORECASE|re.UNICODE)
            if m:
                log.debug('found episode number with regexp %s' % ep_re)
                season, episode = m.groups()
                self.season = int(season)
                self.episode = int(episode)
                self.valid = True
                self.id = "S%sE%s" % (self.season, self.episode)
                return

        # search for id
        for id_re in self.id_regexps:
            m = re.search(id_re, self.data, re.IGNORECASE|re.UNICODE)
            if m:
                log.debug('found id with regexp %s' % id_re)
                self.id = string.join(m.groups(), '-')
                self.valid = True
                return

        log.debug('FAIL: unable to find any id')

    def identifier(self):
        """Return identifier for parsed episode"""
        if not self.valid: raise Exception('Serie flagged invalid')
        return self.id

    def __str__(self):
        valid = 'INVALID'
        if self.valid:
            valid = 'OK'
        return 'serie: %s, id: %s season: %s episode: %s quality: %s status: %s' % (str(self.name), str(self.id), str(self.season), str(self.episode), str(self.quality), valid)


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
        
    """

    def register(self, manager, parser):
        manager.register(event='filter', keyword='series', callback=self.filter_series)
        manager.register(event='input', keyword='series', callback=self.input_series, order=65535)
        manager.register(event='exit', keyword='series', callback=self.learn_succeeded)

    def validate(self, config):
        """Validate configuration format for this module"""
        from validator import ListValidator
        serie = ListValidator()
        # just plain names
        serie.accept(str)
        # or "bundles" with serie name as key ..
        bundle = serie.accept(dict)
        # prevent invalid indentation level
        bundle.reject_keys(['path', 'timeframe', 'name_patterns', 'ep_patterns', 'id_patterns'])
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
        serie.validate(config)
        return serie.errors.messages

    def input_series(self, feed):
        """Retrieve stored series from cache, incase they've been expired from feed while waiting"""
        for name in feed.config.get('series', []):
            if type(name) == types.DictType:
                name = name.items()[0][0]
            serie = feed.cache.get(name)
            if not serie: continue
            for identifier in serie.keys():
                for quality in SerieParser.qualities:
                    if quality=='info': continue # a hack, info dict is not quality
                    entry = serie[identifier].get(quality)
                    if not entry: continue
                    # check if episode is still in feed, if not then add it
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

    def filter_series(self, feed):
        for name in feed.config.get('series', []):
            # start with default settings
            conf = feed.manager.get_settings('series', {})
            if type(name) == types.DictType:
                name, conf = name.items()[0]
                # merge with default settings
                conf = feed.manager.get_settings('series', conf)

            def get_as_array(conf, key):
                v = conf.get(key, [])
                if type(v) in types.StringTypes:
                    return [v]
                return v

            ep_patterns = get_as_array(conf, 'ep_patterns')
            id_patterns = get_as_array(conf, 'id_patterns')
            name_patterns = get_as_array(conf, 'name_patterns')

            series = {} # ie. S1E2: [Serie, Serie, ..]
            for entry in feed.entries:
                serie = SerieParser()
                serie.name = name
                serie.data = entry['title']
                serie.ep_regexps.extend(ep_patterns)
                serie.id_regexps.extend(id_patterns)
                serie.name_regexps.extend(name_patterns)
                serie.parse()
                if not serie.valid:
                    log.debug('%s is not serie %s' % (entry['title'], name))
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
                    log.debug('Rejecting all instances of %s' % identifier)
                    for ep in eps:
                        feed.reject(ep.entry)
                    continue

                # timeframe present
                if conf.has_key('timeframe'):
                    tconf = conf.get('timeframe')
                    hours = tconf.get('hours', 0)
                    enough = tconf.get('enough', '720p')

                    if not enough in SerieParser.qualities:
                        log.error('Parameter enough has unknown value: %s' % enough)

                    # scan for enough, starting from worst quality (reverse)
                    eps.reverse()
                    found_enough = False
                    for ep in eps:
                        if self.cmp_quality(enough, ep.quality) >= 0: # 1=greater, 0=equal, -1=does not meet
                            log.debug('Episode %s meets quality %s' % (ep.entry['title'], enough))
                            self.accept_serie(feed, ep)
                            found_enough = True
                            break
                    if found_enough:
                        continue
                            
                    # timeframe
                    diff = datetime.today() - self.get_first_seen(feed, best)
                    age_hours = divmod(diff.seconds, 60*60)[0]
                    log.debug('age_hours %i - %s ' % (age_hours, best))
                    log.debug('best ep in %i hours is %s' % (hours, best))
                    if age_hours >= hours:
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
        fs = feed.cache.get(serie.name)[serie.identifier()]['info']['first_seen']
        return datetime(*fs)

    def downloaded(self, feed, serie):
        """Return true if this episode of serie is downloaded"""
        cache = feed.cache.get(serie.name)
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
        cache = feed.cache.storedefault(serie.name, {}, 30)
        episode = cache.setdefault(serie.identifier(), {})
        info = episode.setdefault('info', {})
        # store and make first seen time
        info.setdefault('first_seen', list(datetime.today().timetuple())[:-4])
        info.setdefault('downloaded', False)
        ec = {}
        ec['title'] = entry['title']
        ec['url'] = entry['url']
        episode.setdefault(serie.quality, ec)

    def mark_downloaded(self, feed, serie):
        log.debug('marking %s as downloaded' % serie.identifier())
        cache = feed.cache.get(serie.name)
        cache[serie.identifier()]['info']['downloaded'] = True

    def learn_succeeded(self, feed):
        for entry in feed.get_succeeded_entries():
            serie = entry.get('serie_parser')
            if serie:
                self.mark_downloaded(feed, serie)
            else:
                log.debug('Entry %s is not valid serie' % entry['title'])
