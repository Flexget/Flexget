import re

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup

logger = logger.bind(name='yamtrack_list')


class YamtrackList:
    schema = {
        'type': 'object',
        'properties': {
            'host': {'type': 'string', 'default': 'http://localhost:8000'},
            'session_id': {'type': 'string'},
            'list': {'type': 'integer'},
            'type': {'type': 'string', 'enum': ['tv', 'movie', 'all'], 'default': 'all'},
        },
        'required': ['session_id', 'list'],
        'additionalProperties': False,
    }

    def on_task_input(self, task, config) -> list[Entry]:
        logger.verbose('Retrieving Yamtrack list: %s', config['list'])

        self.task = task
        self.config = config
        self.url = f'{config["host"]}/list/{config["list"]}'
        self.params = {'page': 1}
        self.cookies = {'sessionid': config['session_id']}

        return self.parse_html_list()

    def fetch_page(self):
        logger.debug('Requesting: %s, %s, %s', self.url, self.params, self.cookies)

        try:
            page = self.task.requests.get(
                self.url, params=self.params, cookies=self.cookies, allow_redirects=False
            )
        except RequestException as e:
            raise plugin.PluginError(str(e))

        if page.status_code != 200:
            raise plugin.PluginError(
                f'Unable to get Yamtrack list. HTML status code was: {page.status_code}.'
            )

        return page

    def parse_html_list(self) -> list[Entry]:
        logger.debug('Parsing Yamtrack list: %s', self.url)

        page = self.fetch_page()
        soup = get_soup(page.text)

        try:
            total_item_count = int(re.search(r'(\d+) items', page.text).group(1))
            logger.verbose('Yamtrack list contains %s items', total_item_count)

            items = soup.find(id='items-grid').find_all(True, recursive=False)
        except Exception:
            total_item_count = 0
            items = []

        if not total_item_count:
            logger.verbose('Nothing found in Yamtrack list: %s', self.config['list'])
            return []

        while len(items) < total_item_count:
            self.params['page'] += 1
            page = self.fetch_page()
            soup = get_soup(page.text)
            try:
                new_items = soup.find(id='items-grid').find_all(True, recursive=False)
                items.extend(new_items)
            except Exception:
                raise plugin.PluginError('Received invalid list data')

        return self.parse_entries(items)

    def parse_entries(self, items) -> list[Entry]:
        entries = []

        for item in items:
            entry = self.parse_entry(item)
            if entry:
                entries.append(entry)

        return entries

    def parse_entry(self, item) -> Entry:
        tmdb_metadata = re.search(
            r'^/details/tmdb/(?P<type>\w+)/(?P<id>\d+)/', item.find('a')['href']
        ).groupdict()

        if self.config['type'] not in ['all', tmdb_metadata['type']]:
            return None

        entry = Entry()
        title = item.find('img')['alt']
        entry['title'] = title
        entry['url'] = f'https://www.themoviedb.org/{tmdb_metadata["type"]}/{tmdb_metadata["id"]}'

        entry['tmdb_name'] = title
        entry['tmdb_id'] = tmdb_metadata['id']

        if tmdb_metadata['type'] == 'movie':
            entry['movie_name'] = title
        elif tmdb_metadata['type'] == 'tv':
            entry['series_name'] = title

        return entry


@event('plugin.register')
def register_plugin():
    plugin.register(YamtrackList, 'yamtrack_list', api_ver=2)
