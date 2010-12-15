import logging
from flexget.plugin import priority, register_plugin
from flexget.utils.titles import SeriesParser
from flexget.utils.titles.parser import ParseWarning
import re

log = logging.getLogger('metanfo_series')


class MetainfoSeries(object):
    """
    Check if entry appears to be a series, and populate series info if so.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    # Run after series plugin so we don't try to re-parse it's entries
    @priority(120)
    def on_feed_metainfo(self, feed):
        # Don't run if we are disabled
        if not feed.config.get('metainfo_series', True):
            return
        for entry in feed.entries:
            # If series plugin already parsed this, don't touch it.
            if entry.get('series_name'):
                continue
            self.guess_entry(entry)

    def guess_entry(self, entry):
        """Populates series_* fields for entries that are successfully parsed."""
        if entry.get('series_parser') and entry['series_parser'].valid:
            # Return true if we already parsed this, false if series plugin parsed it
            return entry.get('series_guessed')
        parser = self.guess_series(entry['title'])
        if parser:
            entry['series_name'] = parser.name
            entry['series_season'] = parser.season
            entry['series_episode'] = parser.episode
            entry['series_id'] = parser.identifier
            entry['series_guessed'] = True
            entry['series_parser'] = parser
            return True
        return False

    def guess_series(self, title):
        """Returns a valid series parser if this :title: appears to be a series"""

        parser = SeriesParser()
        # We need to replace certain characters with spaces to make sure episode parsing works right
        # We don't remove anything, as the match positions should line up with the original title
        clean_title = re.sub('[_.,\[\]\(\):]', ' ', title)
        match = parser.parse_episode(clean_title)
        if match:
            if parser.parse_unwanted(clean_title):
                return
            elif match[2].start() > 1:
                # We start using the original title here, so we can properly ignore unwanted prefixes.
                # Look for unwanted prefixes to find out where the series title starts
                start = 0
                prefix = re.match('|'.join(parser.ignore_prefix_regexps), title)
                if prefix:
                    start = prefix.end()
                # If an episode id is found, assume everything before it is series name
                name = title[start:match[2].start()]
                # Replace . and _ with spaces
                name = re.sub('[\._ ]+', ' ', name).strip()
                # Normalize capitalization to title case
                name = name.title()
                # If we didn't get a series name, return
                if not name:
                    return
                parser.name = name
                parser.data = title
                try:
                    parser.parse()
                except ParseWarning, pw:
                    log.debug('ParseWarning: %s' % pw.value)
                if parser.valid:
                    return parser

register_plugin(MetainfoSeries, 'metainfo_series')
