import random
import re
import time
import unicodedata

from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.simple_persistence import SimplePersistence
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='magnetdl')


class Page404Error(Exception):
    pass


class MagnetDL:
    """Creates entries from magnetdl categories"""

    url = 'https://www.magnetdl.com'

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'category': {
                        'type': 'string',
                        'enum': ['software', 'movies', 'games', 'e-books', 'tv', 'music'],
                    },
                    'pages': {'type': 'integer', 'minimum': 1, 'maximum': 30, 'default': 5},
                },
                'additionalProperties': False,
            },
        ]
    }

    def _url(self, category, page):
        return self.url + '/download/' + category + '/' + (str(page) if page > 0 else '')

    def parse_page(self, scraper, url: str):
        try:
            logger.debug('page url: {}', url)
            page = scraper.get(url)
        except RequestException as e:
            raise plugin.PluginError(str(e))
        if page.status_code == 404:
            raise Page404Error()
        if page.status_code != 200:
            raise plugin.PluginError(f'HTTP Request failed {page.status_code}. Url: {url}')

        soup = get_soup(page.text)
        soup_table = soup.find('table', class_='download')
        if not soup_table:
            # very likely no result
            return
        table_tbody = soup_table.find('tbody')
        if not table_tbody:
            raise plugin.PluginError('Parsing crashed, no tbody, please report the issue')

        trs = table_tbody.find_all('tr')
        if not trs:
            logger.critical('Nothing to parse')
            return
        for tr in trs:
            try:
                magnet_td = tr.find('td', class_='m')
                if not magnet_td:
                    # skip empty trs
                    continue
                magnet_a = magnet_td.find('a')
                magnet = magnet_a['href']
                title_td = tr.find('td', class_='n')
                title_a = title_td.find('a')
                title = title_a['title']
                seed_td = tr.find('td', class_='s')
                seed = int(seed_td.text)
                leech = int(tr.find('td', class_='l').text)
                content_size = parse_filesize(seed_td.previous_sibling.text)
                yield Entry(
                    url=magnet,
                    title=title,
                    torrent_seeds=seed,
                    torrent_leech=leech,
                    content_size=content_size,
                )
            except AttributeError as e:
                raise plugin.PluginError('Parsing crashed, please report the issue') from e

    @cached('magnetdl', persist='4 minutes')
    def on_task_input(self, task, config):
        try:
            import cloudscraper
        except ImportError as e:
            logger.debug('Error importing cloudscraper: {}', e)
            raise plugin.DependencyError(
                issued_by='cfscraper',
                missing='cloudscraper',
                message='CLOudscraper module required. ImportError: %s' % e,
            )

        scraper = cloudscraper.create_scraper()
        category = config['category']
        persistence = SimplePersistence(plugin='magnetdl')
        last_magnet = persistence.get(category, None)
        logger.debug('last_magnet: {}', last_magnet)
        first_magnet = None
        stop = False

        for page in range(0, config['pages']):
            logger.verbose('Retrieving {} page {}', category, page + 1)
            url = self._url(category, page)
            logger.debug('Url: {}', url)
            try:
                for entry in self.parse_page(scraper, url):
                    if first_magnet is None:
                        first_magnet = entry['url']
                        logger.debug('Set first_magnet to {}', first_magnet)
                        persistence[category] = first_magnet
                    if last_magnet == entry['url']:
                        logger.debug('Found page where we have left, stopping')
                        stop = True
                    yield entry
            except Page404Error:
                logger.warning('Page {} returned 404, stopping', page)
                return
            if stop:
                return
            time.sleep(random.randint(1, 5))

    # Search API method
    def search(self, task, entry, config):
        if not config:
            return
        try:
            import cloudscraper
        except ImportError as e:
            logger.debug('Error importing cloudscraper: {}', e)
            raise plugin.DependencyError(
                issued_by='cfscraper',
                missing='cloudscraper',
                message='CLOudscraper module required. ImportError: %s' % e,
            )
        scraper = cloudscraper.create_scraper()
        entries = []
        for search_string in entry.get('search_strings', [entry['title']]):
            logger.debug('Searching `{}`', search_string)
            try:
                # magnetdl.com search path accepts only [a-z0-9] and dashes/-
                normalized_string = ''.join(
                    c
                    for c in unicodedata.normalize('NFD', search_string)
                    if unicodedata.category(c) != 'Mn'
                )
                term = re.sub('[^a-z0-9]', '-', normalized_string.lower())
                term = re.sub('-+', '-', term).strip('-')
                # note: weird url convention, uses first letter of search term
                slash = term[0]
                url = f'https://www.magnetdl.com/{slash}/{term}/'
                for entry in self.parse_page(scraper, url):
                    entries.append(entry)
            except Page404Error:
                logger.warning('Url {} returned 404', url)
                return entries
            time.sleep(random.randint(1, 5))
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(MagnetDL, 'magnetdl', api_ver=2, interfaces=['task', 'search'])
