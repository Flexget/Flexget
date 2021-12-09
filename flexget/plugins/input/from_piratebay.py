from urllib.parse import urlencode

from loguru import logger

from flexget import plugin
from flexget.components.sites.utils import torrent_availability
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='from_piratebay')

URL = 'https://apibay.org'

LISTS = ['top', 'top48h', 'recent']

# from lowest to highest, selecting a rank automatically accept higher ranks
RANKS = ['all', 'user', 'trusted', 'vip', 'helper', 'moderator', 'supermod']

CATEGORIES = {
    'All': 0,
    'Audio': 100,
    'Music': 101,
    'Audio books': 102,
    'Sound clips': 103,
    'FLAC': 104,
    'Audio Other': 199,
    'Video': 200,
    'Movies': 201,
    'Movies DVDR': 202,
    'Music videos': 203,
    'Movie clips': 204,
    'TV shows': 205,
    'Video Handheld': 206,
    'HD - Movies': 207,
    'HD - TV shows': 208,
    '3D': 209,
    'Video Other': 299,
    'Applications': 300,
    'App Windows': 301,
    'App Mac': 302,
    'App UNIX': 303,
    'App Handheld': 304,
    'App IOS (iPad/iPhone)': 305,
    'App Android': 306,
    'App Other OS': 399,
    'Games': 400,
    'Game PC': 401,
    'Game Mac': 402,
    'Game PSx': 403,
    'Game XBOX360': 404,
    'Game Wii': 405,
    'Game Handheld': 406,
    'Game IOS (iPad/iPhone)': 407,
    'Game Android': 408,
    'Game Other': 499,
    'Porn': 500,
    'Porn Movies': 501,
    'Porn Movies DVDR': 502,
    'Porn Pictures': 503,
    'Porn Games': 504,
    'Porn HD - Movies': 505,
    'Porn Movie clips': 506,
    'Porn Other': 599,
    'Other': 600,
    'E-books': 601,
    'Comics': 602,
    'Pictures': 603,
    'Covers': 604,
    'Physibles': 605,
    'Other Other': 699,
}

# default trackers for magnet links
TRACKERS = [
    'udp://tracker.coppersurfer.tk:6969/announce',
    'udp://9.rarbg.to:2920/announce',
    'udp://tracker.opentrackr.org:1337',
    'udp://tracker.internetwarriors.net:1337/announce',
    'udp://tracker.leechers-paradise.org:6969/announce',
    'udp://tracker.coppersurfer.tk:6969/announce',
    'udp://tracker.pirateparty.gr:6969/announce',
    'udp://tracker.cyberia.is:6969/announce',
]


class FromPirateBay:
    """
    Return torrent listing from piratebay api.

    ::

      url: <piratebay api mirror, for example: https://apibay.org or http://piratebayztemzmv.onion>
      category: <str|int>. Accept a category name or ID.
      list: <top|top48h|recent>
      rank: <any|member|vip|trusted> Minimum rank of torrent uploader


    Example::

      from_piratebay:
        url: https://apibay.org
        category: HD - Movies
        list: top
        rank: all

      OR:

      from_piratebay:
        category: HD - Movies
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string', 'default': URL, 'format': 'url'},
            'category': {
                'oneOf': [
                    {'type': 'string', 'enum': list(CATEGORIES)},
                    {'type': 'integer'},
                ]
            },
            'list': {'type': 'string', 'enum': list(LISTS), 'default': 'top'},
            'rank': {'type': 'string', 'enum': list(RANKS), 'default': 'all'},
        },
        'required': ['list'],
        'additionalProperties': False,
    }

    def on_task_input(self, task, config):
        url = config.get('url').rstrip('/')
        list = config.get('list')
        rank = RANKS.index(config.get('rank', 'all'))
        if isinstance(config.get('category'), int):
            category = config['category']
        else:
            category = CATEGORIES.get(config.get('category', 'All'))

        if list == 'top':
            if category:
                list_url = f'{url}/precompiled/data_top100_{category}.json'
            else:
                list_url = f'{url}/precompiled/data_top100_all.json'
        elif list == 'top48h':
            if category:
                list_url = f'{url}/precompiled/data_top100_48h_{category}.json'
            else:
                list_url = f'{url}/precompiled/data_top100_48h.json'
        else:  # list == 'recent'
            if category:
                list_url = f'{url}/q.php?q=category:{category}'
            else:
                # top100_recent has multiple pages, starting at data_top100_recent.json, then data_top100_recent_1.json
                # to 30, and appears not filtered by categories
                list_url = f'{url}/precompiled/data_top100_recent.json'

        json_results = task.requests.get(list_url).json()

        for result in json_results:
            if result['id'] == '0':
                # no result found
                break
            if RANKS.index(result['status'].lower()) < rank:
                # filter by rank/status, useful for recent torrents
                logger.debug(
                    f"{result['name']} has been dropped due to low rank ({result['status']})."
                )
                continue
            yield self.json_to_entry(result)

    @staticmethod
    def info_hash_to_magnet(info_hash: str, name: str) -> str:
        magnet = {'xt': f"urn:btih:{info_hash}", 'dn': name, 'tr': TRACKERS}
        magnet_qs = urlencode(magnet, doseq=True, safe=':')
        magnet_uri = f"magnet:?{magnet_qs}"
        return magnet_uri

    def json_to_entry(self, json_result: dict) -> Entry:
        entry = Entry()
        entry['title'] = json_result['name']
        entry['torrent_seeds'] = int(json_result['seeders'])
        entry['torrent_leeches'] = int(json_result['leechers'])
        entry['torrent_timestamp'] = int(json_result['added'])  # custom field for sorting by date
        entry['torrent_availability'] = torrent_availability(
            entry['torrent_seeds'], entry['torrent_leeches']
        )
        entry['content_size'] = int(round(int(json_result['size']) / (1024 * 1024)))
        entry['torrent_info_hash'] = json_result['info_hash']
        entry['url'] = self.info_hash_to_magnet(json_result['info_hash'], json_result['name'])
        return entry


@event('plugin.register')
def register_plugin():
    plugin.register(FromPirateBay, 'from_piratebay', api_ver=2)
