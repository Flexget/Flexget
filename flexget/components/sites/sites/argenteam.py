from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.components.sites.utils import normalize_scene

log = logging.getLogger('argenteam')


class SearchArgenteam(object):
    """ Argenteam
    Search plugin which gives results from www.argenteam.net, latin american (Argentina) web.

    Configuration:
      - force_subtitles: [yes/no] #Force download release with subtitles made by aRGENTeaM. Default is yes

    Example
      argenteam:
        force_subtitles: yes
    """

    schema = {
        'type': 'object',
        'properties': {'force_subtitles': {'type': 'boolean', 'default': True}},
        "additionalProperties": False,
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
                params = {'q': normalize_scene(search_string)}
                resp = task.requests.get(self.base_url + 'search', params=params)
                log.debug('Requesting: %s', resp.url)
                response = resp.json()
            except RequestException as e:
                log.error('Argenteam request failed: %s', e)
                return

            if not response:
                log.debug('Empty response from Argenteam')
                continue

            if not response.get('total'):
                log.debug('No results found for %s', search_string)
                continue

            results = response.get('results')
            if results[0]['type'] == 'tvshow':
                log.error('Argenteam type tvshow not supported yet.')
                continue

            url = '{}{}?id={}'.format(self.base_url, results[0]['type'], results[0]['id'])
            try:
                resp = task.requests.get(url)
                log.debug('Requesting releases for: %s', url)
                response = resp.json()
            except RequestException as e:
                log.error('Argenteam request failed: %s', e)
                return

            for release in response['releases']:
                for torrent in release['torrents']:
                    if (
                        config.get('force_subtitles')
                        and release['subtitles']
                        or not config.get('force_subtitles')
                    ):
                        e = Entry()

                        e['title'] = ' '.join(
                            (
                                search_string,
                                release['source'],
                                release['codec'],
                                release['team'],
                                release['tags'],
                            )
                        )
                        e['url'] = torrent['uri']

                        # Save aRGENTeaM subtitle URL for this release
                        if 'subtitles' in release:
                            e['argenteam_subtitle'] = release['subtitles'][0]['uri']
                            log.debug('Argenteam subtitle found: %s', e['argenteam_subtitle'])

                        if 'tvdb' in response:
                            e['tvdb_id'] = response['tvdb']
                        if 'info' in response and 'imdb' in response['info']:
                            e['imdb_id'] = response['info']['imdb']

                        entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchArgenteam, 'argenteam', interfaces=['search'], api_ver=2)
