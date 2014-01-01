from __future__ import unicode_literals, division, absolute_import
import logging
from string import capwords
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.series import populate_entry_fields
from flexget.utils.titles import SeriesParser
from flexget.utils.titles.parser import ParseWarning

log = logging.getLogger('metanfo_series')


class MetainfoSeries(object):
    """
    Check if entry appears to be a series, and populate series info if so.
    """

    schema = {'type': 'boolean'}

    # Run after series plugin so we don't try to re-parse it's entries
    @plugin.priority(120)
    def on_task_metainfo(self, task, config):
        # Don't run if we are disabled
        if config is False:
            return
        for entry in task.entries:
            # If series plugin already parsed this, don't touch it.
            if entry.get('series_name'):
                continue
            self.guess_entry(entry)

    def guess_entry(self, entry, allow_seasonless=False):
        """Populates series_* fields for entries that are successfully parsed."""
        if entry.get('series_parser') and entry['series_parser'].valid:
            # Return true if we already parsed this, false if series plugin parsed it
            return entry.get('series_guessed')
        parser = self.guess_series(entry['title'], allow_seasonless=allow_seasonless, quality=entry.get('quality'))
        if parser:
            populate_entry_fields(entry, parser)
            entry['series_guessed'] = True
            return True
        return False

    def guess_series(self, title, allow_seasonless=False, quality=None):
        """Returns a valid series parser if this `title` appears to be a series"""

        parser = SeriesParser(identified_by='auto', allow_seasonless=allow_seasonless)
        # We need to replace certain characters with spaces to make sure episode parsing works right
        # We don't remove anything, as the match positions should line up with the original title
        clean_title = re.sub('[_.,\[\]\(\):]', ' ', title)
        if parser.parse_unwanted(clean_title):
            return
        match = parser.parse_date(clean_title)
        if match:
            parser.identified_by = 'date'
        else:
            match = parser.parse_episode(clean_title)
            if match and parser.parse_unwanted(clean_title):
                return
            parser.identified_by = 'ep'
        if not match:
            return
        if match['match'].start() > 1:
            # We start using the original title here, so we can properly ignore unwanted prefixes.
            # Look for unwanted prefixes to find out where the series title starts
            start = 0
            prefix = re.match('|'.join(parser.ignore_prefixes), title)
            if prefix:
                start = prefix.end()
            # If an episode id is found, assume everything before it is series name
            name = title[start:match['match'].start()]
            # Remove possible episode title from series name (anything after a ' - ')
            name = name.split(' - ')[0]
            # Replace some special characters with spaces
            name = re.sub('[\._\(\) ]+', ' ', name).strip(' -')
            # Normalize capitalization to title case
            name = capwords(name)
            # If we didn't get a series name, return
            if not name:
                return
            parser.name = name
            parser.data = title
            try:
                parser.parse(data=title, quality=quality)
            except ParseWarning as pw:
                log.debug('ParseWarning: %s' % pw.value)
            if parser.valid:
                return parser


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoSeries, 'metainfo_series', api_ver=2)
