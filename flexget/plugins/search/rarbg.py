from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.requests import Session, get, TimedLimiter, RequestException
from flexget.utils.search import normalize_scene

log = logging.getLogger('rarbg')

requests = Session()
requests.add_domain_limiter(TimedLimiter('torrentapi.org', '2.3 seconds'))  # they only allow 1 request per 2 seconds

CATEGORIES = {
    'all': 0,

    # Movies
    'x264 720p': 45,
    'x264 1080p': 44,
    'XviD': 14,
    'Full BD': 42,

    # TV
    'HDTV': 41,
    'SDTV': 18
}


class SearchRarBG(object):
    """
        RarBG search plugin.

        To perform search against single category:

        rarbg:
            category: x264 720p

        To perform search against multiple categories:

        rarbg:
            category:
                - x264 720p
                - x264 1080p

        Movie categories accepted: x264 720p, x264 1080p, XviD, Full BD
        TV categories accepted: HDTV, SDTV

        You can use also use category ID manually if you so desire (eg. x264 720p is actually category id '45')
    """

    schema = {
        'type': 'object',
        'properties': {
            'category': one_or_more({
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'string', 'enum': list(CATEGORIES)},
                ]}),
            'sorted_by': {'type': 'string', 'enum': ['seeders', 'leechers', 'last'], 'default': 'last'},
            # min_seeders and min_leechers seem to be working again
            'min_seeders': {'type': 'integer', 'default': 0},
            'min_leechers': {'type': 'integer', 'default': 0},
            'limit': {'type': 'integer', 'enum': [25, 50, 100], 'default': 25},
            'ranked': {'type': 'boolean', 'default': True},
            'use_tvdb': {'type': 'boolean', 'default': False},
        },
        "additionalProperties": False
    }

    base_url = 'https://torrentapi.org/pubapi_v2.php'

    def get_token(self):
        # Don't use a session as tokens are not affected by domain limit
        try:
            r = get(self.base_url, params={'get_token': 'get_token', 'format': 'json'}).json()
            token = r.get('token')
            log.debug('RarBG token: %s' % token)
            return token
        except RequestException as e:
            log.debug('Could not retrieve RarBG token: %s', e.args[0])

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for entries on RarBG
        """

        categories = config.get('category', 'all')
        # Ensure categories a list
        if not isinstance(categories, list):
            categories = [categories]
        # Convert named category to its respective category id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
        category_url_fragment = ';'.join(str(c) for c in categories)

        entries = set()

        token = self.get_token()
        if not token:
            log.error('Could not retrieve token. Abandoning search.')
            return entries

        params = {'mode': 'search', 'token': token, 'ranked': int(config['ranked']),
                  'min_seeders': config['min_seeders'], 'min_leechers': config['min_leechers'],
                  'sort': config['sorted_by'], 'category': category_url_fragment, 'format': 'json_extended',
                  'app_id': 'flexget'}

        for search_string in entry.get('search_strings', [entry['title']]):
            params.pop('search_string', None)
            params.pop('search_imdb', None)
            params.pop('search_tvdb', None)

            if entry.get('movie_name'):
                params['search_imdb'] = entry.get('imdb_id')
            else:
                query = normalize_scene(search_string)
                query_url_fragment = query.encode('utf8')
                params['search_string'] = query_url_fragment
                if config['use_tvdb']:
                    plugin.get_plugin_by_name('thetvdb_lookup').instance.lazy_series_lookup(entry)
                    params['search_tvdb'] = entry.get('tvdb_id')
                    log.debug('Using tvdb id %s', entry.get('tvdb_id'))
            try:
                page = requests.get(self.base_url, params=params)
                log.debug('requesting: %s', page.url)
            except RequestException as e:
                log.error('RarBG request failed: %s' % e.args[0])
                continue
            r = page.json()
            # error code 20 just means no results were found
            if r.get('error_code') == 20:
                searched_string = params.get('search_string') or 'imdb={0}'.format(params.get('search_imdb')) or \
                                  'tvdb={0}'.format(params.get('tvdb_id'))
                log.debug('No results found for %s', searched_string)
                continue
            elif r.get('error'):
                log.error('Error code %s: %s', r.get('error_code'), r.get('error'))
                continue
            else:
                for result in r.get('torrent_results'):
                    e = Entry()

                    e['title'] = result.get('title')
                    e['url'] = result.get('download')
                    e['torrent_seeds'] = int(result.get('seeders'))
                    e['torrent_leeches'] = int(result.get('leechers'))
                    e['content_size'] = int(result.get('size')) / 1024 / 1024
                    episode_info = result.get('episode_info')
                    if episode_info:
                        e['imdb_id'] = episode_info.get('imdb')
                        e['tvdb_id'] = episode_info.get('tvdb')
                        e['tvrage_id'] = episode_info.get('tvrage')

                    entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchRarBG, 'rarbg', groups=['search'], api_ver=2)
