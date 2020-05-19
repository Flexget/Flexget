import re

from loguru import logger

from flexget import plugin
from flexget.components.imdb.utils import extract_id, is_valid_imdb_title_id
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
    """"Creates an entry for each movie in your imdb list."""

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
                'error_oneOf': 'list must be either %s, or a custom list name (lsXXXXXXXXX)'
                % ', '.join(USER_LISTS),
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
    def on_task_input(self, task, config):
        config = self.prepare_config(config)

        # Create movie entries by parsing imdb list page(s) html using beautifulsoup
        logger.verbose('Retrieving imdb list: {}', config['list'])

        headers = {'Accept-Language': config.get('force_language')}
        params = {'view': 'detail', 'page': 1}
        if config['list'] in ['watchlist', 'ratings', 'checkins']:
            url = 'http://www.imdb.com/user/%s/%s' % (config['user_id'], config['list'])
            if config['list'] == 'watchlist':
                params = {'view': 'detail'}
        else:
            url = 'http://www.imdb.com/list/%s' % config['list']
        if 'all' not in config['type']:
            title_types = [TITLE_TYPE_MAP[title_type] for title_type in config['type']]
            params['title_type'] = ','.join(title_types)
            params['sort'] = 'list_order%2Casc'

        if config['list'] == 'watchlist':
            entries = self.parse_react_widget(task, config, url, params, headers)
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
                'Unable to get imdb list. Either list is private or does not exist.'
                + ' Html status code was: %d.' % page.status_code
            )
        return page

    def parse_react_widget(self, task, config, url, params, headers):
        page = self.fetch_page(task, url, params, headers)
        try:
            json_vars = json.loads(
                re.search(r'IMDbReactInitialState.push\((.+?)\);\n', page.text).group(1)
            )
        except (TypeError, AttributeError, ValueError) as e:
            raise plugin.PluginError(
                'Unable to get imdb list from imdb react widget.'
                + ' Either the list is empty or the imdb parser of the imdb_watchlist plugin is broken.'
                + ' Original error: %s.' % str(e)
            )
        total_item_count = 0
        if 'list' in json_vars and 'items' in json_vars['list']:
            total_item_count = len(json_vars['list']['items'])
        if not total_item_count:
            logger.verbose('No movies were found in imdb list: {}', config['list'])
            return []
        imdb_ids = []
        for item in json_vars['list']['items']:
            if is_valid_imdb_title_id(item.get('const')):
                imdb_ids.append(item['const'])
        params = {'ids': ','.join(imdb_ids)}
        url = 'http://www.imdb.com/title/data'
        try:
            json_data = self.fetch_page(task, url, params, headers).json()
        except (ValueError, TypeError) as e:
            raise plugin.PluginError(
                'Unable to get imdb list from imdb JSON API.'
                + ' Either the list is empty or the imdb parser of the imdb_watchlist plugin is broken.'
                + ' Original error: %s.' % str(e)
            )
        logger.verbose('imdb list contains {} items', len(json_data))
        logger.debug(
            'First entry (imdb id: {}) looks like this: {}', imdb_ids[0], json_data[imdb_ids[0]]
        )
        entries = []
        for imdb_id in imdb_ids:
            entry = Entry()
            if not (
                'title' in json_data[imdb_id]
                and 'primary' in json_data[imdb_id]['title']
                and 'href' in json_data[imdb_id]['title']['primary']
                and 'title' in json_data[imdb_id]['title']['primary']
            ):
                logger.debug('no title or link found for item {}, skipping', imdb_id)
                continue
            if 'type' in json_data[imdb_id]['title']:
                entry['imdb_type'] = json_data[imdb_id]['title']['type']
            title = json_data[imdb_id]['title']['primary']['title']
            entry['title'] = title
            if 'year' in json_data[imdb_id]['title']['primary']:
                year = json_data[imdb_id]['title']['primary']['year'][0]
                entry['title'] += ' (%s)' % year
                entry['imdb_year'] = year
            entry['url'] = json_data[imdb_id]['title']['primary']['href']
            entry['imdb_id'] = imdb_id
            entry['imdb_name'] = entry['title']
            entries.append(entry)
        return entries

    def parse_html_list(self, task, config, url, params, headers):
        page = self.fetch_page(task, url, params, headers)
        soup = get_soup(page.text)
        try:
            item_text = soup.find('div', class_='lister-total-num-results').string.split()
            total_item_count = int(item_text[0].replace(',', ''))
            logger.verbose('imdb list contains {} items', total_item_count)
        except AttributeError:
            total_item_count = 0
        except (ValueError, TypeError) as e:
            # TODO Something is wrong if we get a ValueError, I think
            raise plugin.PluginError(
                'Received invalid movie count: %s ; %s'
                % (soup.find('div', class_='lister-total-num-results').string, e)
            )

        if not total_item_count:
            logger.verbose('No movies were found in imdb list: {}', config['list'])
            return

        entries = []
        items_processed = 0
        page_no = 1
        while items_processed < total_item_count:
            # Fetch the next page unless we've just begun
            if items_processed:
                page_no += 1
                params['page'] = page_no
                page = self.fetch_page(task, url, params, headers)
                soup = get_soup(page.text)

            items = soup.find_all('div', class_='lister-item')
            if not items:
                logger.debug('no items found on page: {}, aborting.', url)
                break
            logger.debug('{} items found on page {}', len(items), page_no)

            for item in items:
                items_processed += 1
                a = item.find('h3', class_='lister-item-header').find('a')
                if not a:
                    logger.debug('no title link found for row, skipping')
                    continue

                link = ('http://www.imdb.com' + a.get('href')).rstrip('/')
                entry = Entry()
                entry['title'] = a.text
                try:
                    year = int(item.find('span', class_='lister-item-year').text)
                    entry['title'] += ' (%s)' % year
                    entry['imdb_year'] = year
                except (ValueError, TypeError):
                    pass
                entry['url'] = link
                entry['imdb_id'] = extract_id(link)
                entry['imdb_name'] = entry['title']
                entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(ImdbWatchlist, 'imdb_watchlist', api_ver=2)
