from loguru import logger

from flexget import plugin
from flexget.components.sites.utils import normalize_scene
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.requests import RequestException, TimedLimiter

logger = logger.bind(name='rarbg')

CATEGORIES = {
    'all': 0,
    # Movies
    'x264': 17,
    'x264 720p': 45,
    'x264 1080p': 44,
    'x264 3D': 47,
    'XviD': 14,
    'XviD 720p': 48,
    'Full BD': 42,
    # TV
    'HDTV': 41,
    'SDTV': 18,
    # Adult
    'XXX': 4,
    # Music
    'MusicMP3': 23,
    'MusicFLAC': 25,
    # Games
    'Games/PC ISO': 27,
    'Games/PC RIP': 28,
    'Games/PS3': 40,
    'Games/XBOX-360': 32,
    'Software/PC ISO': 33,
    # E-Books
    'e-Books': 35,
}


class SearchRarBG:
    """
    RarBG search plugin. Implements https://torrentapi.org/apidocs_v2.txt

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
            'category': one_or_more(
                {'oneOf': [{'type': 'integer'}, {'type': 'string', 'enum': list(CATEGORIES)}]}
            ),
            'sorted_by': {
                'type': 'string',
                'enum': ['seeders', 'leechers', 'last'],
                'default': 'last',
            },
            # min_seeders and min_leechers seem to be working again
            'min_seeders': {'type': 'integer', 'default': 0},
            'min_leechers': {'type': 'integer', 'default': 0},
            'limit': {'type': 'integer', 'enum': [25, 50, 100], 'default': 25},
            'ranked': {'type': 'boolean', 'default': True},
            'use_tvdb': {'type': 'boolean', 'default': False},
        },
        "additionalProperties": False,
    }

    base_url = 'https://torrentapi.org/pubapi_v2.php'
    token = None

    def get_token(self, session, refresh=False):
        if refresh or not self.token:
            try:
                response = session.get(
                    self.base_url,
                    params={'get_token': 'get_token', 'format': 'json', 'app_id': 'flexget'},
                ).json()
                self.token = response.get('token')
                logger.debug('RarBG token: {}', self.token)
            except RequestException as e:
                logger.opt(exception=True).debug('Could not retrieve RarBG token')
                raise PluginError('Could not retrieve token: %s' % e)
        return self.token

    def get(self, session, params, token_error=False):
        """
        Simple get-wrapper that allows updating invalid tokens

        :param session: The requests session to use
        :param params: the params to be passed to requests
        :param token_error: whether or not we previously have had token errors, if True we should fetch a new one
        :return: json response
        """
        params['token'] = self.get_token(session=session, refresh=token_error)
        try:
            response = session.get(self.base_url, params=params)
            logger.debug('requesting: {}', response.url)
            response = response.json()
        except RequestException as e:
            logger.error('Rarbg request failed: {}', e)
            return

        # error code 1, 2 and 4 pertain to token errors
        if response.get('error_code') in [1, 2, 4]:
            logger.debug(
                'Invalid token. Error {}: {}', response['error_code'], response.get('error')
            )
            if token_error:
                raise PluginError('Could not retrieve a valid token: %s' % response.get('error'))
            return self.get(session=session, params=params, token_error=True)

        return response

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """
        Search for entries on RarBG
        """

        session = task.requests
        # Don't override user specified limiters from domain_delay
        # Use a longer delay than strictly necessary due to issues
        # https://github.com/Flexget/Flexget/issues/3705
        session.add_domain_limiter(TimedLimiter('torrentapi.org', '6 seconds'), replace=False)

        categories = config.get('category', 'all')
        # Ensure categories a list
        if not isinstance(categories, list):
            categories = [categories]
        # Convert named category to its respective category id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
        category_url_fragment = ';'.join(str(c) for c in categories)

        entries = set()

        params = {
            'mode': 'search',
            'ranked': int(config['ranked']),
            'min_seeders': config['min_seeders'],
            'min_leechers': config['min_leechers'],
            'sort': config['sorted_by'],
            'category': category_url_fragment,
            'format': 'json_extended',
            'app_id': 'flexget',
        }

        for search_string in entry.get('search_strings', [entry['title']]):
            params.pop('search_string', None)
            params.pop('search_imdb', None)
            params.pop('search_tvdb', None)

            if entry.get('movie_name') and entry.get('imdb_id'):
                params['search_imdb'] = entry.get('imdb_id')
            else:
                query = normalize_scene(search_string)
                query_url_fragment = query.encode('utf8')
                params['search_string'] = query_url_fragment
                if config['use_tvdb']:
                    plugin.get('thetvdb_lookup', self).lazy_series_lookup(entry, 'en')
                    params['search_tvdb'] = entry.get('tvdb_id')
                    logger.debug('Using tvdb id {}', entry.get('tvdb_id'))

            response = self.get(session=session, params=params)
            if not response:
                continue

            # error code 10 and 20 just mean no results were found
            if response.get('error_code') in [10, 20]:
                searched_string = (
                    params.get('search_string')
                    or 'imdb={}'.format(params.get('search_imdb'))
                    or 'tvdb={}'.format(params.get('tvdb_id'))
                )
                logger.debug(
                    'No results found for {}. Message from rarbg: {}',
                    searched_string,
                    response.get('error'),
                )
                continue
            elif response.get('error'):
                logger.error(
                    'Error code {}: {}', response.get('error_code'), response.get('error')
                )
                continue
            else:
                for result in response.get('torrent_results'):
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
    plugin.register(SearchRarBG, 'rarbg', interfaces=['search'], api_ver=2)
