import re

from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.soup import get_soup

logger = logger.bind(name='anidb_list')
USER_ID_RE = r'^\d{1,6}$'


class AnidbList:
    """"Creates an entry for each movie or series in your AniDB wishlist."""

    anidb_url = 'http://anidb.net/perl-bin/'

    default_user_agent = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36 (KHTML, like Gecko) '
        'Chrome/69.0.3497.100 Safari/537.36'
    )

    MODE_MAP = {'all': 0, 'undefined': 1, 'watch': 2, 'get': 3, 'blacklist': 4, 'buddy': 11}

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'integer',
                'pattern': USER_ID_RE,
                'error_pattern': 'user_id must be in the form XXXXXXX',
            },
            'type': {'type': 'string', 'enum': ['shows', 'movies', 'ovas'], 'default': 'movies'},
            'mode': {'type': 'string', 'enum': list(MODE_MAP.keys()), 'default': 'all'},
            'pass': {'type': 'string'},
            'strip_dates': {'type': 'boolean', 'default': False},
        },
        'additionalProperties': False,
        'required': ['user_id'],
        'error_required': 'user_id is required',
    }

    def _build_url_params(self, config):
        params = {'show': 'mywishlist', 'uid': config['user_id']}
        if config.get('mode') != 'all':
            params['mode'] = config['mode']
        if config.get('pass'):
            params['pass'] = config['pass']
        return params

    @cached('anidb_list', persist='2 hours')
    def on_task_input(self, task, config):
        # Create entries by parsing AniDB wishlist page html using beautifulsoup
        logger.verbose('Retrieving AniDB list: mywishlist:{}', config['mode'])

        task_headers = task.requests.headers.copy()
        task_headers['User-Agent'] = self.default_user_agent

        try:
            page = task.requests.get(
                self.anidb_url + 'animedb.pl',
                params=self._build_url_params(config),
                headers=task_headers,
            )
        except RequestException as e:
            raise plugin.PluginError(str(e))
        if page.status_code != 200:
            raise plugin.PluginError(
                'Unable to get AniDB list. Either the list is private or does not exist.'
            )

        entry_type = ''

        if config['type'] == 'movies':
            entry_type = 'Type: Movie'
        elif config['type'] == 'shows':
            entry_type = 'Type: TV Series'
        elif config['type'] == 'ovas':
            entry_type = 'Type: OVA'

        while True:
            soup = get_soup(page.text)
            soup_table = soup.find('table', class_='wishlist').find('tbody')

            trs = soup_table.find_all('tr')
            if not trs:
                logger.verbose('No movies were found in AniDB list: mywishlist')
                return
            for tr in trs:
                if tr.find('span', title=entry_type):
                    a = tr.find('td', class_='name').find('a')
                    if not a:
                        logger.debug('No title link found for the row, skipping')
                        continue

                    anime_title = a.string
                    if config.get('strip_dates'):
                        # Remove year from end of series name if present
                        anime_title = re.sub(r'\s+\(\d{4}\)$', '', anime_title)

                    entry = Entry()
                    entry['title'] = anime_title
                    entry['url'] = self.anidb_url + a.get('href')
                    entry['anidb_id'] = tr['id'][
                        1:
                    ]  # The <tr> tag's id is "aN..." where "N..." is the anime id
                    logger.debug('{} id is {}', entry['title'], entry['anidb_id'])
                    entry['anidb_name'] = entry['title']
                    yield entry
                else:
                    logger.verbose('Entry does not match the requested type')
            try:
                # Try to get the link to the next page.
                next_link = soup.find('li', class_='next').find('a')['href']
            except TypeError:
                # If it isn't there, there are no more pages to be crawled.
                logger.verbose('No more pages on the wishlist.')
                break
            comp_link = self.anidb_url + next_link
            logger.debug('Requesting: {}', comp_link)
            try:
                page = task.requests.get(comp_link, headers=task_headers)
            except RequestException as e:
                logger.error(str(e))
            if page.status_code != 200:
                logger.warning('Unable to retrieve next page of wishlist.')
                break


@event('plugin.register')
def register_plugin():
    plugin.register(AnidbList, 'anidb_list', api_ver=2, interfaces=['task'])
