from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget.plugins.parsers.parser_common import normalize_name, remove_dirt
from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.series import populate_entry_fields
from flexget.plugin import get_plugin_by_name

log = logging.getLogger('metainfo_series')


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

    def guess_entry(self, entry, allow_seasonless=False, config=None):
        """
        Populates series_* fields for entries that are successfully parsed.

        :param dict config: A series config to be used. This will also cause 'path' and 'set' fields to be populated.
        """
        if entry.get('series_parser') and entry['series_parser'].valid:
            # Return true if we already parsed this, false if series plugin parsed it
            return entry.get('series_guessed')
        parsed = get_plugin_by_name('parsing').instance.parse_series(data=entry['title'], identified_by='auto',
                                                                     allow_seasonless=allow_seasonless)
        if parsed and parsed.valid:
            parsed.name = normalize_name(remove_dirt(parsed.name))
            populate_entry_fields(entry, parsed, config)
            entry['series_guessed'] = True
            return True
        return False


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoSeries, 'metainfo_series', api_ver=2)
