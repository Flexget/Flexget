from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from collections import MutableSet

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.plugins.internal.api_tvdb import TVDBRequest, lookup_series
from flexget.utils.requests import RequestException
from flexget.utils.tools import split_title_year

log = logging.getLogger('thetvdb_list')


class TheTVDBSet(MutableSet):
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'account_id': {'type': 'string'},
            'strip_dates': {'type': 'boolean'}
        },
        'required': ['username', 'account_id'],
        'additionalProperties': False
    }

    @property
    def immutable(self):
        return False

    def _from_iterable(self, it):
        return set(it)

    def __init__(self, config):
        self.config = config
        self._items = None

    def __iter__(self):
        return iter([item for item in self.items])

    def __len__(self):
        return len(self.items)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def get(self, entry):
        return self._find_entry(entry)

    @property
    def items(self):
        if self._items is None:
            try:
                req = TVDBRequest(username=self.config['username'], account_id=self.config['account_id']).get(
                    'user/favorites')
                series_ids = [int(f_id) for f_id in req['favorites'] if f_id != '']
            except RequestException as e:
                raise PluginError('Error retrieving favorites from thetvdb: %s' % str(e))
            self._items = []
            for series_id in series_ids:
                # Lookup the series name from the id
                try:
                    series = lookup_series(tvdb_id=series_id)
                except LookupError as e:
                    log.error('Error looking up %s from thetvdb: %s' % (series_id, e.args[0]))
                else:
                    series_name = series.name
                    if self.config.get('strip_dates'):
                        # Remove year from end of series name if present
                        series_name, _ = split_title_year(series_name)
                    entry = Entry()
                    entry['title'] = entry['series_name'] = series_name
                    entry['url'] = 'http://thetvdb.com/index.php?tab=series&id={}'.format(str(series.id))
                    entry['tvdb_id'] = str(series.id)
                    self._items.append(entry)
        return self._items

    def invalidate_cache(self):
        self._items = None

    def add(self, entry):
        if not entry.get('tvdb_id'):
            log.verbose('entry does not have `tvdb_id`, cannot add to list. Consider using a lookup plugin`')
            return
        try:
            TVDBRequest(username=self.config['username'], account_id=self.config['account_id']).put(
                'user/favorites/{}'.format(entry['tvdb_id']))
        except RequestException as e:
            log.error('Could not add tvdb_id {} to favourites list: {}'.format(entry['tvdb_id'], e))
        self.invalidate_cache()

    def discard(self, entry):
        if not entry.get('tvdb_id'):
            log.verbose('entry does not have `tvdb_id`, cannot remove from list. Consider using a lookup plugin`')
            return
        try:
            TVDBRequest(username=self.config['username'], account_id=self.config['account_id']).delete(
                'user/favorites/{}'.format(entry['tvdb_id']))
        except RequestException as e:
            log.error('Could not add tvdb_id {} to favourites list: {}'.format(entry['tvdb_id'], e))
        self.invalidate_cache()

    def _find_entry(self, entry):
        if not entry.get('tvdb_id'):
            log.debug('entry does not have `tvdb_id`, skipping: {}'.format(entry))
            return
        for item in self.items:
            if item['tvdb_id'] == entry['tvdb_id']:
                return item

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return True


class TheTVDBList(object):
    schema = TheTVDBSet.schema

    def get_list(self, config):
        return TheTVDBSet(config)

    def on_task_input(self, task, config):
        return list(TheTVDBSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(TheTVDBList, 'thetvdb_list', api_ver=2, groups=['list'])
