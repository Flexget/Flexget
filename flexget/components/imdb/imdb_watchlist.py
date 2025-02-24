from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup

logger = logger.bind(name='imdb_watchlist')
USER_ID_RE = r'^ur\d{7,9}$'
CUSTOM_LIST_RE = r'^ls\d{7,10}$'
USER_LISTS = ['watchlist', 'ratings', 'checkins']
TITLE_TYPE_MAP = {
    'movies': 'movie',
    'short films': 'short',
    'games': 'videoGame',
    'mini series': 'tvMiniSeries',
    'shows': 'tvSeries',
    'episodes': 'tvEpisode',
    'tv movies': 'tvMovie',
    'tv specials': 'tvSpecial',
    'videos': 'video',
}


class ImdbWatchlist:
    """Creates an entry for each movie in your imdb list."""

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'string',
                'pattern': USER_ID_RE,
                'error_pattern': 'user_id must be in the form urXXXXXXX',
            },
            'list': {
                'type': 'string',
                'oneOf': [{'enum': USER_LISTS}, {'pattern': CUSTOM_LIST_RE}],
                'error_oneOf': 'list must be either {}, or a custom list name (lsXXXXXXXXX)'.format(
                    ', '.join(USER_LISTS)
                ),
            },
            'force_language': {'type': 'string', 'default': 'en-us'},
            'type': {
                'oneOf': [
                    one_or_more(
                        {'type': 'string', 'enum': list(TITLE_TYPE_MAP.keys())}, unique_items=True
                    ),
                    {'type': 'string', 'enum': ['all']},
                ]
            },
            'strip_dates': {'type': 'boolean', 'default': False},
        },
        'additionalProperties': False,
        'required': ['list'],
        'anyOf': [
            {'required': ['user_id']},
            {'properties': {'list': {'pattern': CUSTOM_LIST_RE}}},
        ],
        'error_anyOf': 'user_id is required if not using a custom list (lsXXXXXXXXX format)',
    }

    def prepare_config(self, config):
        if 'type' not in config:
            config['type'] = ['all']

        if not isinstance(config['type'], list):
            config['type'] = [config['type']]

        return config

    @cached('imdb_watchlist', persist='2 hours')
    def on_task_input(self, task, config) -> list[Entry]:
        config = self.prepare_config(config)

        # Create movie entries by parsing imdb list page(s) html using beautifulsoup
        logger.verbose('Retrieving imdb list: {}', config['list'])

        headers = {'Accept-Language': config.get('force_language')}
        params = {'view': 'detail', 'page': 1}
        if config['list'] in USER_LISTS:
            url = 'http://www.imdb.com/user/{}/{}'.format(config['user_id'], config['list'])
            if config['list'] == 'watchlist':
                params = {'view': 'detail'}
        else:
            url = 'http://www.imdb.com/list/{}'.format(config['list'])
        if 'all' not in config['type']:
            title_types = [TITLE_TYPE_MAP[title_type] for title_type in config['type']]
            params['title_type'] = ','.join(title_types)
            params['sort'] = 'list_order%2Casc'

        if config['list'] == 'watchlist':
            entries = self.parse_html_list(
                task, config, url, params, headers, kind='predefinedList'
            )
        else:
            entries = self.parse_html_list(task, config, url, params, headers)
        return entries

    def fetch_page(self, task, url, params, headers):
        logger.debug('Requesting: {} {}', url, headers)
        try:
            page = task.requests.get(url, params=params, headers=headers)
        except RequestException as e:
            raise plugin.PluginError(str(e))
        if page.status_code != 200:
            raise plugin.PluginError(
                f'Unable to get imdb list. Either list is private or does not exist. '
                f'Html status code was: {page.status_code}.'
            )
        return page

    def parse_html_list(self, task, config, url, params, headers, kind='list') -> list[Entry]:
        page = self.fetch_page(task, url, params, headers)
        soup = get_soup(page.text)
        try:
            query_result = json.loads(
                soup.find('script', id='__NEXT_DATA__', type='application/json').string
            )
            total_item_count = query_result['props']['pageProps']['totalItems']
            items = query_result['props']['pageProps']['mainColumnData'][kind][
                'titleListItemSearch'
            ]['edges']
            logger.verbose('imdb list contains {} items', total_item_count)
        except Exception:
            total_item_count = 0
            items = []

        if not total_item_count:
            logger.verbose('Nothing found in imdb list: {}', config['list'])
            return []

        page_no = 1

        while len(items) < total_item_count:
            page_no += 1
            params['page'] = page_no
            page = self.fetch_page(task, url, params, headers)
            soup = get_soup(page.text)
            try:
                query_result = json.loads(
                    soup.find('script', id='__NEXT_DATA__', type='application/json').string
                )
                items.extend(
                    query_result['props']['pageProps']['mainColumnData'][kind][
                        'titleListItemSearch'
                    ]['edges']
                )
            except Exception:
                raise plugin.PluginError('Received invalid list data')

        return [self.parse_entry(item['listItem'], config) for item in items]

    def parse_entry(self, item, config) -> Entry:
        entry = Entry()
        title = item['titleText']['text']
        title_type = item['titleType']['id']

        entry['title'] = title
        entry['url'] = entry['imdb_url'] = f"https://www.imdb.com/title/{item['id']}/"
        entry['imdb_id'] = item['id']

        entry['imdb_name'] = title
        entry['imdb_original_name'] = item['originalTitleText']['text']
        if title_type in ['movie', 'tvMovie']:
            entry['movie_name'] = title
        elif title_type in ['tvSeries', 'tvMiniSeries']:
            entry['series_name'] = title

        if item['releaseYear']:
            year = item['releaseYear']['year']
            entry['imdb_year'] = year

            if title_type in ['movie', 'tvMovie']:
                entry['movie_year'] = year
            elif title_type in ['tvSeries', 'tvMiniSeries']:
                entry['series_year'] = year

            if not config.get('strip_dates'):
                entry['title'] += f' ({year})'

        rating = item['ratingsSummary']['aggregateRating']
        if isinstance(rating, float):
            entry['imdb_user_score'] = entry['imdb_score'] = rating
            entry['imdb_votes'] = item['ratingsSummary']['voteCount']

        return entry


@event('plugin.register')
def register_plugin():
    plugin.register(ImdbWatchlist, 'imdb_watchlist', api_ver=2)
