import logging
from flexget.plugin import *
from flexget.utils.titles import SeriesParser
import re

log = logging.getLogger('metanfo_series')


class MetainfoSeries(object):
    """
    Check if entry appears to be a series, and populate series info if so.
    """
    
    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_metainfo(self, feed):
        # Don't run if we are disabled
        if not feed.config.get('metainfo_series', True):
            return
        for entry in feed.entries:
            match = self.guess_series(entry['title'])
            if match:
                entry['series_name'] = match[0]
                entry['series_season'] = match[1]
                entry['series_episode'] = match[2]
                entry['series_parser'] = match[3]
                entry['series_guessed'] = True

    def guess_series(self, title):
        """Returns tuple of (series_name, season, episode, parser) if found, else None"""
        
        # Clean the data for parsing
        parser = SeriesParser()
        match = parser.parse_episode(title)
        if match:
            if match[0] is None:
                return
            elif match[2].start() > 1:
                # Look for unwanted prefixes to find out where the series title starts
                start = 0
                prefix = re.match('|'.join(parser.ignore_prefix_regexps), title)
                if prefix:
                    start = prefix.end()
                # If an episode id is found, assume everything before it is series name
                name = title[start:match[2].start()]
                # Replace . and _ with spaces
                name = re.sub('[\._]', ' ', name)
                name = ' '.join(name.split())
                # If we didn't get a series name, return
                if not name:
                    return
                season = match[0]
                episode = match[1]
                parser.name = name
                parser.data = title
                parser.season = season
                parser.episode = episode
                parser.valid = True
                return (name, season, episode, parser)

register_plugin(MetainfoSeries, 'metainfo_series', builtin=True)
