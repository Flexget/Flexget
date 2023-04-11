import re
from urllib.parse import quote_plus

from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.components.sites.utils import normalize_scene, torrent_availability
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.requests import Session as RequestSession
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='fuzer')

requests = RequestSession()

CATEGORIES = {
    # Movies
    'HD Movies': 9,
    'XviD': 7,
    'BRRip': 59,
    'Israeli HD Movies': 61,
    'Israeli Movies': 60,
    'DVDR': 58,
    'Dubbed Movies': 83,
    # TV
    'HD Shows': 10,
    'Shows': 8,
    'Israeli HD Shows': 63,
    'Israeli Shows': 62,
    'Dubbed Shows': 84,
    # Anime
    'Anime': 65,
    # FuzePacks
    'Movie Packs': 73,
    'Shows Packs': 76,
}


class UrlRewriteFuzer:
    schema = {
        'type': 'object',
        'properties': {
            'cookie_password': {'type': 'string'},
            'user_id': {'type': 'integer'},
            'rss_key': {'type': 'string'},
            'category': one_or_more(
                {'oneOf': [{'type': 'string', 'enum': list(CATEGORIES)}, {'type': 'integer'}]}
            ),
        },
        'required': ['user_id', 'cookie_password', 'rss_key'],
        'additionalProperties': False,
    }

    def get_fuzer_soup(self, search_term, categories_list):
        params = {'matchquery': 'any', 'ref_': 'advanced'}
        query = '{}&{}'.format(search_term, '&'.join(categories_list))
        try:
            page = requests.get(
                f'https://www.fuzer.me/browse.php?query={query}',
                params=params,
                cookies=self.cookies,
            )
        except RequestException as e:
            raise PluginError(f'Could not connect to Fuzer: {e}')

        if 'login' in page.url:
            raise PluginError('Could not fetch results from Fuzer. Check config')

        logger.debug('Using {} as fuzer search url', page.url)
        return get_soup(page.content)

    def extract_entry_from_soup(self, soup):
        table = soup.find('div', {'id': 'main_table'})
        if table is None:
            raise PluginError('Could not fetch results table from Fuzer, aborting')

        logger.trace('fuzer results table: {}', table)
        table = table.find('table', {'class': 'table_info'})
        if len(table.find_all('tr')) == 1:
            logger.debug('No search results were returned from Fuzer, continuing')
            return []

        entries = []
        for tr in table.find_all("tr"):
            if not tr.get('class') or 'colhead_dark' in tr.get('class'):
                continue
            name = tr.find('div', {'class': 'main_title'}).find('a').text
            torrent_name = re.search(
                '\\n(.*)', tr.find('div', {'style': 'float: right;'}).find('a')['title']
            ).group(1)
            attachment_link = tr.find('div', {'style': 'float: right;'}).find('a')['href']
            attachment_id = re.search(r'attachmentid=(\d+)', attachment_link).group(1)
            raw_size = tr.find_all('td', {'class': 'inline_info'})[0].text.strip()
            seeders = int(tr.find_all('td', {'class': 'inline_info'})[2].text)
            leechers = int(tr.find_all('td', {'class': 'inline_info'})[3].text)

            e = Entry()
            e['title'] = name
            final_url = 'https://www.fuzer.me/rss/torrent.php/{}/{}/{}/{}'.format(
                attachment_id, self.user_id, self.rss_key, torrent_name
            )

            logger.debug('RSS-ified download link: {}', final_url)
            e['url'] = final_url

            e['torrent_seeds'] = seeders
            e['torrent_leeches'] = leechers
            e['torrent_availability'] = torrent_availability(
                e['torrent_seeds'], e['torrent_leeches']
            )

            size = re.search(r'(\d+(?:[.,]\d+)*)\s?([KMGTP]B)', raw_size)
            e['content_size'] = parse_filesize(size.group(0))

            entries.append(e)
        return entries

    @plugin.internet(logger)
    def search(self, task, entry, config=None):
        """
        Search for name from fuzer.
        """
        self.rss_key = config['rss_key']
        self.user_id = config['user_id']

        self.cookies = {
            'fzr2lastactivity': '0',
            'fzr2lastvisit': '',
            'fzr2password': config['cookie_password'],
            'fzr2sessionhash': '',
            'fzr2userid': str(self.user_id),
        }

        category = config.get('category', [0])
        # Make sure categories is a list
        if not isinstance(category, list):
            category = [category]

        # If there are any text categories, turn them into their id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in category]
        c_list = ['c{}={}'.format(quote_plus('[]'), c) for c in categories]

        entries = []
        if entry.get('imdb_id'):
            logger.debug("imdb_id '{}' detected, using in search.", entry['imdb_id'])
            soup = self.get_fuzer_soup(entry['imdb_id'], c_list)
            entries = self.extract_entry_from_soup(soup)
            if entries:
                for e in list(entries):
                    e['imdb_id'] = entry.get('imdb_id')
        else:
            for search_string in entry.get('search_strings', [entry['title']]):
                query = normalize_scene(search_string)
                text = quote_plus(query.encode('windows-1255'))
                soup = self.get_fuzer_soup(text, c_list)
                entries += self.extract_entry_from_soup(soup)
        return (
            sorted(entries, reverse=True, key=lambda x: x.get('torrent_availability'))
            if entries
            else []
        )


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteFuzer, 'fuzer', interfaces=['search'], api_ver=2)
