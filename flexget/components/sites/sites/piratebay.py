import re
from urllib.parse import urlencode, urlparse

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.components.sites.utils import normalize_unicode, torrent_availability
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='piratebay')

URL = 'https://apibay.org'  # for TOR: http://piratebayztemzmv.onion

CATEGORIES = {
    'all': 0,
    'audio': 100,
    'music': 101,
    'video': 200,
    'movies': 201,
    'tv': 205,
    'highres movies': 207,
    'highres tv': 208,
    'comics': 602,
}

# try to maintain compatibility with old config
SORT = {
    'default': 'torrent_availability',
    'date': 'torrent_timestamp',
    'size': 'content_size',
    'seeds': 'torrent_seeds',
    'leechers': 'torrent_leeches',
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


class UrlRewritePirateBay:
    """PirateBay urlrewriter."""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'default': URL, 'format': 'url'},
                    'category': {
                        'oneOf': [
                            {'type': 'string', 'enum': list(CATEGORIES)},
                            {'type': 'integer'},
                        ]
                    },
                    'sort_by': {'type': 'string', 'enum': list(SORT)},
                    'sort_reverse': {'type': 'boolean'},
                },
                'additionalProperties': False,
            },
        ]
    }

    url = None

    def __init__(self):
        self.set_urls(URL)

    def on_task_start(self, task, config=None):
        if not isinstance(config, dict):
            config = {}
        self.set_urls(config.get('url', URL))

    def set_urls(self, url):
        url = url.rstrip('/')
        if self.url != url:
            self.url = url
            parsed_url = urlparse(url)
            escaped_url_scheme = re.escape(parsed_url.scheme)
            escaped_url_netloc = re.escape(parsed_url.netloc)
            # most api mirrors share the same domain with frontend, except thepiratebay.org which uses apibay.org
            # some api mirrors might contain path, for ex https://pirateproxy.surf/api?url=/q.php?q=ubuntu&cat=0
            # valid URLs are https://piratebay.org/description.php?id=\d+ and https://apibay.org/description.php?id=\d+
            self.url_match = re.compile(
                fr'^{escaped_url_scheme}://(?:thepiratebay\.org(?:\:\d+)?|{escaped_url_netloc})/description\.php\?id=(\d+)$'
            )
            self.url_search = re.compile(
                fr'^(?:https?://thepiratebay\.org(?:\:\d+)?|{escaped_url_scheme}://{escaped_url_netloc})/search\.php\?q=.*$'
            )

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.endswith('.torrent'):
            return False
        return any((self.url_match.match(url), self.url_search.match(url)))

    # urlrewriter API
    def url_rewrite(self, task, entry):
        if 'url' not in entry:
            logger.error("Didn't actually get a URL...")
        else:
            logger.debug('Got the URL: {}', entry['url'])
        if self.url_search.match(entry['url']):
            # use search
            results = self.search(task, entry)
            if not results:
                raise UrlRewritingError("No search results found")
            # TODO: Close matching was taken out of search methods, this may need to be fixed to be more picky
            entry['url'] = results[0]['url']
        else:
            torrent_id = self.url_match.match(entry['url']).group(1)
            url = f"{self.url}/t.php?id={torrent_id}"
            logger.debug('Getting info for torrent ID {}', torrent_id)
            json_result = task.requests.get(url).json()
            if json_result['id'] == '0':
                raise UrlRewritingError(f"Torrent with ID {torrent_id} does not exist.")
            entry['url'] = self.info_hash_to_magnet(json_result['info_hash'], json_result['name'])

    @plugin.internet(logger)
    def search(self, task, entry, config=None):
        """
        Search for name from piratebay.
        """
        if not isinstance(config, dict):
            config = {}
        self.set_urls(config.get('url', URL))
        sort = SORT.get(config.get('sort_by', 'default'))
        sort_reverse = bool(config.get('sort_reverse', 'True'))
        if isinstance(config.get('category'), int):
            category = config['category']
        else:
            category = CATEGORIES.get(config.get('category', 'all'))

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            # query = normalize_unicode(search_string)
            params = {'q': search_string, 'cat': category}
            url = f"{self.url}/q.php"
            json_results = task.requests.get(url, params=params).json()
            if not json_results:
                raise plugin.PluginError("Error while searching piratebay for %s.", search_string)
            for result in json_results:
                if result['id'] == '0':
                    # JSON when no results found: [{ "id":"0", "name":"No results returned", ... }]
                    break
                entry = self.json_to_entry(result)
                entries.add(entry)

        return sorted(entries, reverse=sort_reverse, key=lambda x: x.get(sort))

    # convert an info_hash string to a magnet uri
    @staticmethod
    def info_hash_to_magnet(info_hash: str, name: str) -> str:
        magnet = {'xt': f"urn:btih:{info_hash}", 'dn': name, 'tr': TRACKERS}
        magnet_qs = urlencode(magnet, doseq=True, safe=':')
        magnet_uri = f"magnet:?{magnet_qs}"
        return magnet_uri

    # convert a single json result to an Entry
    def json_to_entry(self, json_result: dict) -> Entry:
        entry = Entry()
        entry['title'] = json_result['name']
        entry['torrent_seeds'] = int(json_result['seeders'])
        entry['torrent_leeches'] = int(json_result['leechers'])
        entry['torrent_timestamp'] = int(json_result['added'])  # custom field for sorting by date
        entry['torrent_availability'] = torrent_availability(
            entry['torrent_seeds'], entry['torrent_leeches']
        )
        entry['content_size'] = int(
            round(int(json_result['size']) / (1024 * 1024))
        )  # content_size is in MiB
        entry['torrent_info_hash'] = json_result['info_hash']
        entry['url'] = self.info_hash_to_magnet(json_result['info_hash'], json_result['name'])
        return entry


@event('plugin.register')
def register_plugin():
    plugin.register(
        UrlRewritePirateBay, 'piratebay', interfaces=['urlrewriter', 'search', 'task'], api_ver=2
    )
