import logging
import re
import types
from datetime import tzinfo, timedelta, datetime

# might be better of just being function which returns dict ...
class SerieParser:

    qualities = ['1080p', '1080', '720p', '720', 'hr', 'dvd', 'hdtv', 'dsr', 'unknown']
    season_ep_regexps = ['s(\d+)e(\d+)', 's(\d+)ep(\d+)', '(\d+)x(\d+)']
    
    def __init__(self, name, title):
        self.name = name
        self.item = title
        # parse produces these
        self.season = None
        self.episode = None
        self.quality = 'unknown'
        # false if item does not match serie
        self.valid = False
        # parse
        self.parse()
        # optional for storing entry from which this instance is made from
        self.entry = None

    def parse(self):
        serie = self.name.replace('.', ' ').lower()
        item = self.item.replace('.', ' ').replace('_', ' ').lower()
        serie_data = serie.split(' ')
        item_data = item.split(' ')
        for part in serie_data:
            if part in item_data:
                item_data.remove(part)
            else:
                #logging.debug('part %s not found from %s' % (part, item_data))
                # leave this invalid
                return

        for part in item_data:
            # search for quality
            if part in self.qualities:
                self.quality = part
            # search for season and episode number
            for sre in self.season_ep_regexps:
                m = re.search(sre, part)
                if m:
                    if len(m.groups())==2:
                        season, episode = m.groups()
                        self.season = int(season)
                        self.episode = int(episode)
                        self.valid = True
                        break

    def identifier(self):
        """Return episode in form of S<Season>E<Episode>"""
        if not self.valid: raise Exception('Serie flagged invalid')
        return "S%sE%s" % (self.season, self.episode)

    def __str__(self):
        valid = 'INVALID'
        if self.valid:
            valid = 'OK'
        return 'serie: %s, season: %s episode: %s quality: %s status: %s' % (str(self.name), str(self.season), str(self.episode), str(self.quality), valid)
        


class FilterSeries:

    """
        Intelligent filter for tv-series. This solves duplicate downloads
        problem that occurs when using patterns (regexp) matching since same
        episode is often released by multiple groups.

        Example configuration:

        series:
          - some serie
          - another serie
          
        If "some serie" and "another serie" have understandable episode
        numbering entry is downloaded only once.

        So if we get same episode twice:
        
        Some.Serie.S2E10.More.Text
        Some.Serie.S2E10.Something.Else

        Only first file is downloaded.

        In future there may be way to affect which entry will be selected.
    """

    def register(self, manager, parser):
        manager.register(instance=self, type="filter", keyword="series", callback=self.filter_series)
        manager.register(instance=self, type="input", keyword="series", callback=self.input_series, order=65535)
        manager.register(instance=self, type="exit", keyword="series", callback=self.learn_succeeded)

    def input_series(self, feed):
        """Retrieve stored series from cache, incase they've been expired from feed while waiting"""
        for name in feed.config.get('series', []):
            conf = {}
            if type(name) == types.DictType:
                name, conf = name.items()[0]

            serie = feed.cache.get(name)
            if not serie: continue
            for identifier in serie.keys():
                for quality in SerieParser.qualities:
                    if quality=='info': continue
                    entry = serie[identifier].get(quality)
                    if not entry: continue
                    # check if some input already added this feed
                    exists = False
                    for feed_entry in feed.entries:
                        if feed_entry['title'] == entry['title'] and feed_entry['url'] == entry['url']:
                            exists = True
                    if not exists:
                        logging.debug('FilterSeries restoring entry %s from cache' % entry['title'])
                        feed.entries.append(entry)


    def filter_series(self, feed):
        for name in feed.config.get('series', []):
            conf = {}
            if type(name) == types.DictType:
                name, conf = name.items()[0]
          
            series = {}
            for entry in feed.entries:
                serie = SerieParser(name, entry['title'])
                if not serie.valid: continue
                serie.entry = entry
                self.store(feed, serie, entry)
                # save for choosing
                eps = series.setdefault(serie.identifier(), [])
                eps.append(serie)
            
            # choose best episode
            for identifier, eps in series.iteritems():
                def sort_by_quality(s1, s2):
                    return cmp(SerieParser.qualities.index(s1.quality), SerieParser.qualities.index(s2.quality))
                eps.sort(sort_by_quality)
                if len(eps)==0:
                    continue
                best = eps[0]

                for ep in eps:
                    logging.debug('FilterSeries ep %s' % ep)

                # if age exceeds timeframe
                diff = datetime.today() - self.get_first_seen(feed, best)
                age_hours = divmod(diff.seconds, 60*60)[0]

                logging.debug('FilterSeries %s age_hours %i' % (best, age_hours))
                
                timeframe = conf.get('best_in', 0)
                logging.debug('FilterSeries best ep in %i hours is %s' % (timeframe, best))

                if age_hours < timeframe or self.downloaded(feed, best):
                    logging.debug('FilterSeries filtering %s, downloaded %s' % (best.entry, self.downloaded(feed, best)))
                    feed.filter(best.entry)
                else:
                    # accept
                    logging.debug('FilterSeries passing %s' % best.entry)
                    best.entry = None # not needed, saves memory ?
                    entry['serie_parser'] = best

    def get_first_seen(self, feed, serie):
        """Return datetime when this episode of serie was first seen"""
        fs = feed.cache.get(serie.name)[serie.identifier()]['info']['first_seen']
        return datetime(*fs)

    def downloaded(self, feed, serie):
        cache = feed.cache.get(serie.name)
        # TODO: add --learn verbose!
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

        cache = feed.cache.storedetault(serie.name, {}, 30)
        episode = cache.setdefault(serie.identifier(), {})
        info = episode.setdefault('info', {})

        # store and make first seen time
        fs = info.setdefault('first_seen', list(datetime.today().timetuple())[:-4] )
        first_seen = datetime(*fs)
        info.setdefault('downloaded', False)

        episode.setdefault(serie.quality, entry)

    def mark_downloaded(self, serie):
        cache = feed.cache.get(serie.name)
        cache[serie.identifier()]['info']['downloaded'] = True

    def learn_succeeded(self, feed):
        for entry in feed.get_succeeded_entries():
            serie = entry.get('serie_parser')
            if serie:
                self.mark_downloaded(serie)

if __name__ == '__main__':
    fs = SerieParser('mock serie', 'Mock.Serie.S04E01.HDTV.XviD-TEST.avi')
    fs.parse()
    print fs
    
