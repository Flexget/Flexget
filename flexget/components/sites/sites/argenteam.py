from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.components.sites.utils import normalize_scene
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='argenteam')


class SearchArgenteam:
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

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """
            Search for releases
        """

        entries = set()

        for search_string in entry.get('search_strings', [entry['title']]):

            try:
                params = {'q': normalize_scene(search_string)}
                resp = task.requests.get(self.base_url + 'search', params=params)
                logger.debug('Requesting: {}', resp.url)
                response = resp.json()
            except RequestException as e:
                logger.error('Argenteam request failed: {}', e)
                return

            if not response:
                logger.debug('Empty response from Argenteam')
                continue

            if not response.get('total'):
                logger.debug('No results found for {}', search_string)
                continue

            results = response.get('results')
            if results[0]['type'] == 'tvshow':
                logger.error('Argenteam type tvshow not supported yet.')
                continue

            url = '{}{}?id={}'.format(self.base_url, results[0]['type'], results[0]['id'])
            try:
                resp = task.requests.get(url)
                logger.debug('Requesting releases for: {}', url)
                response = resp.json()
            except RequestException as e:
                logger.error('Argenteam request failed: {}', e)
                return

            logger.debug('{} releases found.', len(response['releases']))
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
                        if 'subtitles' in release and len(release['subtitles']) > 0:
                            e['argenteam_subtitle'] = release['subtitles'][0]['uri']
                            logger.debug('Argenteam subtitle found: {}', e['argenteam_subtitle'])

                        if 'tvdb' in response:
                            e['tvdb_id'] = response['tvdb']
                        if 'info' in response and 'imdb' in response['info']:
                            e['imdb_id'] = response['info']['imdb']

                        entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchArgenteam, 'argenteam', interfaces=['search'], api_ver=2)
