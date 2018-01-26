from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.requests import Session, TimedLimiter, RequestException
from flexget.utils.search import normalize_scene
from flexget.plugin import PluginError

log = logging.getLogger('argenteam')

requests = Session()

class SearchArgenteam(object):
    """ Argenteam """

    schema = {
        'type': 'object',
        'properties': {
            'subtitles': {'type': 'boolean', 'default': True},
        },
        "additionalProperties": False
    }

    base_url = 'http://www.argenteam.net/api/v1/'

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for releases
        """

        entries = set()

        for search_string in entry.get('search_strings', [entry['title']]):

            try:
                params = { 'q': normalize_scene(search_string) }
                response = requests.get(self.base_url+'search', params=params)
                log.debug('Requesting: %s', response.url)
                response = response.json()
            except RequestException as e:
                log.error('Argenteam request failed: %s', e)
                return

            if not response:
                continue

            if response.get('total') == 0:
                log.debug('No results found for %s', search_string)
                continue
            else:
                results = response.get('results')
                if (results[0]['type'] == 'tvshow'):
                  log.error('Argenteam type tvshow not supported yet.')
                  continue
                url = self.base_url+results[0]['type']+'?id='+`results[0]['id']`
                try:
                    response = requests.get(url)
                    log.debug('Requesting releases for: %s', url)
                    response = response.json()
                except RequestException as e:
                    log.error('Argenteam request failed: %s', e)
                    return

                for release in response['releases']:
                    for torrent in release['torrents']:
                        if ((config.get('subtitles') and release['subtitles']) or (not config.get('subtitles'))):
                            e = Entry()

                            e['title'] = ' '.join((search_string, release['source'], release['codec'], release['team'], release['tags']))
                            e['url'] = torrent['uri']
                            if ('tvdb' in response):
                              e['tvdb'] = response['tvdb']
                            if ('info' in response):
                              if ('imdb' in response['info']):
                                e['imdb'] = response['info']['imdb']

                            entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchArgenteam, 'argenteam', interfaces=['search'], api_ver=2)
