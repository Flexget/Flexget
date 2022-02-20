from enum import Enum, unique

from loguru import logger

from flexget import db_schema, plugin
from flexget.components.sites.utils import torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException
from flexget.utils.requests import Session as RequestSession
from flexget.utils.soup import get_soup

logger = logger.bind(name='hebits')
Base = db_schema.versioned_base('hebits', 0)

requests = RequestSession()


@unique
class HeBitsCategory(Enum):
    movies = 1
    tv = 2
    theater = 3
    software = 4
    games = 5
    music = 6
    books = 7
    movies_packs = 8
    porno = 9
    other = 10


class HeBitsSort(Enum):
    time = 1
    year = 2
    size = 3
    snatched = 4
    seeders = 5
    leechers = 6
    random = 7


class SearchHeBits:
    """
    HeBits search plugin.
    """

    schema = {
        'type': 'object',
        'properties': {
            'userid': {'type': 'number'},
            'session': {'type': 'string'},
            'category': {'type': 'string', 'enum': [value.name for value in HeBitsCategory]},
            'free': {'type': 'boolean'},
            'double': {'type': 'boolean'},
            'triple': {'type': 'boolean'},
            'order_by': {
                'type': 'string',
                'enum': [value.name for value in HeBitsSort],
                'default': HeBitsSort.time.name,
            },
            'order_desc': {'type': 'boolean', 'default': True},
        },
        'required': ['userid', 'session'],
        'additionalProperties': False,
    }

    base_url = 'https://hebits.net/'
    search_url = f'{base_url}ajax.php'
    download_url = f'{base_url}torrents.php'
    user_profile_url = f'{base_url}user.php'

    @staticmethod
    def _fetch_account_info(url, config) -> dict:
        logger.debug('Trying to fetch hebits passkey and authkey from user profile')
        authkey, passkey = None, None
        cookies = {"userid": f"{config['userid']}", "session": f"{config['session']}"}
        response = requests.get(url, cookies=cookies, params={'id': config['userid']})
        user_profile_soup = get_soup(response.text)
        for tag in user_profile_soup.find_all("meta"):
            if tag.get("name", None) == "authkey":
                authkey = tag.get('content')
        for tag in user_profile_soup.find_all("a"):
            if tag.get("id", None) == "passkey":
                passkey = tag.get('onclick').split('\'')[1]
        if not authkey or not passkey:
            raise plugin.PluginError('Could not fetch authkey or passkey, layout change?')
        return {
            'authkey': authkey,
            'passkey': passkey,
        }

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """Search for entries on HeBits"""

        account_info = self._fetch_account_info(self.user_profile_url, config)
        params = {
            'action': 'browse',
            'group_results': 0,
        }
        cookies = {"userid": f"{config['userid']}", "session": f"{config['session']}"}

        if 'category' in config:
            cat = HeBitsCategory[config['category']].value
            params[f'filter_cat[{cat}]'] = 1

        entries = set()
        params['order_by'] = HeBitsSort[config['order_by']].value
        params['order_way'] = 'desc' if config['order_desc'] else 'asc'

        for search_string in entry.get(
            'search_strings', [entry['title'], entry.get('original_title'), entry.get('imdb_id')]
        ):
            params['searchstr'] = search_string
            logger.debug('Using search params: {}', params)
            try:
                page = requests.get(self.search_url, cookies=cookies, params=params)
                page.raise_for_status()
                search_results_response = page.json()
            except RequestException as e:
                logger.error('HeBits request failed: {}', e)
                continue
            if search_results_response['status'] != 'success':
                logger.error('HeBits request failed: server error')
                continue

            search_results = search_results_response['response']['results']
            for result in search_results:
                torrent_id = result['torrents'][0]['torrentId']
                seeders = result['torrents'][0]['seeders']
                leechers = result['torrents'][0]['leechers']
                size = result['torrents'][0]['size'] / 2**20
                title = result['torrents'][0]['release']

                entry = Entry(
                    torrent_seeds=seeders,
                    torrent_leeches=leechers,
                    torrent_availability=torrent_availability(seeders, leechers),
                    content_size=size,
                    title=title,
                    torrent_freeleech=result['torrents'][0]['isFreeleech'],
                    torrent_triple_up=result['torrents'][0]['isUploadX3'],
                    torrent_double_up=result['torrents'][0]['isUploadX2'],
                    url=f"{self.download_url}?action=download&id={torrent_id}&authkey={account_info['authkey']}&torrent_pass={account_info['passkey']}",
                )
                entries.add(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchHeBits, 'hebits', interfaces=['search'], api_ver=2)
