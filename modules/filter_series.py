__instance__ = 'FilterSeries'

import logging
import re

class SerieParser:

    qualities = ['1080p', '1080', '720p', '720', 'hr', 'hdtv', 'dsr']
    season_ep_regexps = ['s(\d+)e(\d+)', 's(\d+)ep(\d+)', '(\d+)x(\d+)']
    
    def __init__(self, serie, item):
        self.serie = serie
        self.item = item
        # parse produces these
        self.season = None
        self.episode = None
        self.quality = None
        # false if item does not match serie
        self.valid = True

    def parse(self):
        serie = self.serie.replace('.', ' ').lower()
        item = self.item.replace('.', ' ').replace('_', ' ').lower()
        serie_data = serie.split(' ')
        item_data = item.split(' ')
        for part in serie_data:
            if part in item_data:
                item_data.remove(part)
            else:
                print 'part %s not found from %s' % (part, item_data)
                self.valid = False
        # it's not serie we are looking for
        if not self.valid: return

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
                        break
        
        print item_data

    def __str__(self):
        if self.valid:
            return '%s, season: %s episode: %s quality: %s' % (self.serie, self.season, self.episode, self.quality)
        else:
            return '%s is not valid for serie %s' % (self.item, self.serie)
        


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

    def register(self, manager):
        # disabled untill implemented
        #manager.register(self, "filter", "series", self.filter_series)
        None

    def filter_series(self, feed):
        None

if __name__ == '__main__':
    fs = SerieParser('stargate atlantis', 'Stargate.Atlantis.S04E01.HDTV.XviD-TEST.avi')
    fs.parse()
    print fs
    
