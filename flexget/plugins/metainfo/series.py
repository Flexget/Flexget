from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import time
from copy import copy

from past.builtins import basestring

from flexget.plugins.parsers.parser_common import normalize_name, remove_dirt, SERIES_ID_TYPES
from flexget import plugin
from flexget.manager import Session
from flexget.event import event
from flexget.plugin import get_plugin_by_name
from flexget.plugins.filter.series import Series

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
        self.evaluate(task.entries, config)

    def evaluate(self, entries, config, series_name=None):
        parsing_plugin = get_plugin_by_name('parsing').instance
        params = self._get_params_from_config(series_name, config)

        if not isinstance(entries, list):
            entries = list(entries)

        for entry in entries:
            # skip processed entries
            if entry.get('series_parser') and entry['series_parser'].valid:
                if series_name:
                    if entry['series_parser'].name.lower() != series_name.lower():
                        continue
                else:
                    continue

            # Quality field may have been manipulated by e.g. assume_quality. Use quality field from entry if available.
            parsed = parsing_plugin.parse_series(entry['title'], name=series_name, **params)
            if not parsed.valid:
                continue
            parsed.field = 'title'

            if not series_name:
                parsed.name = normalize_name(remove_dirt(parsed.name))
                entry['series_guessed'] = True

            log.debug('%s detected as %s, field: %s', entry['title'], parsed, parsed.field)
            self._populate_entry_fields(entry, parsed, config)

    def _get_params_from_config(self, series_name, config):
        # set parser flags flags based on config / database
        identified_by = config.get('identified_by', 'auto')
        if series_name and identified_by == 'auto':
            with Session() as session:
                series = session.query(Series).filter(Series.name == series_name).first()
                if series:
                    # set flag from database
                    identified_by = series.identified_by or 'auto'

        def get_as_array(config, key):
            """Return configuration key as array, even if given as a single string"""
            v = config.get(key, [])
            if isinstance(v, basestring):
                return [v]
            return v

        params = dict(
            identified_by=identified_by,
            alternate_names=get_as_array(config, 'alternate_name'),
            name_regexps=get_as_array(config, 'name_regexp'),
            strict_name=config.get('exact', False),
            allow_groups=get_as_array(config, 'from_group'),
            date_yearfirst=config.get('date_yearfirst'),
            date_dayfirst=config.get('date_dayfirst'),
            special_ids=get_as_array(config, 'special_ids'),
            prefer_specials=config.get('prefer_specials'),
            assume_special=config.get('assume_special')
        )

        for id_type in SERIES_ID_TYPES:
            params[id_type + '_regexps'] = get_as_array(config, id_type + '_regexp')

        return params

    def _populate_entry_fields(self, entry, parser, config):
        """
        Populates all series_fields for given entry based on parser.

        :param parser: A valid result from a series parser used to populate the fields.
        :config dict: If supplied, will use 'path' and 'set' options to populate specified fields.
        """
        entry['series_parser'] = copy(parser)
        # add series, season and episode to entry
        entry['series_name'] = parser.name
        if 'quality' in entry and entry['quality'] != parser.quality:
            log.verbose('Found different quality for %s. Was %s, overriding with %s.' %
                        (entry['title'], entry['quality'], parser.quality))
        entry['quality'] = parser.quality
        entry['proper'] = parser.proper
        entry['proper_count'] = parser.proper_count
        entry['release_group'] = parser.group
        if parser.id_type == 'ep':
            entry['series_season'] = parser.season
            entry['series_episode'] = parser.episode
        elif parser.id_type == 'date':
            entry['series_date'] = parser.id
            entry['series_season'] = parser.id.year
        else:
            entry['series_season'] = time.gmtime().tm_year
        entry['series_episodes'] = parser.episodes
        entry['series_id'] = parser.pack_identifier
        entry['series_id_type'] = parser.id_type

        # If a config is passed in, also look for 'path' and 'set' options to set more fields
        if config:
            # set custom download path
            if 'path' in config:
                log.debug('setting %s custom path to %s', entry['title'], config.get('path'))
                # Just add this to the 'set' dictionary, so that string replacement is done cleanly
                config.setdefault('set', {}).update(path=config['path'])

            # accept info from set: and place into the entry
            if 'set' in config:
                set = plugin.get_plugin_by_name('set')
                set.instance.modify(entry, config.get('set'))


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoSeries, 'metainfo_series', api_ver=2)
