import re
import time
from datetime import datetime
from urllib.parse import urlparse

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.components.sites.utils import normalize_unicode, torrent_availability
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='solidtorrents')

URL = 'https://solidtorrents.net/'

CATEGORIES = (
    "all",
    "Audio",
    "Video",
    "Image",
    "Document",
    "eBook",
    "Program",
    "Android",
    "Archive",
    "Diskimage",
    "Sourcecode",
    "Database",
)


SORT = ("seeders", "leechers", "downloads", "date", "size")


class UrlRewriteSolidTorrents:
    """SolidTorrents urlrewriter."""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'default': URL, 'format': 'url'},
                    'category': {'type': 'string', 'enum': list(CATEGORIES)},
                    'sort_by': {'type': 'string', 'enum': list(SORT)},
                    'reverse': {'type': 'boolean'},
                    'remove_potentially_unsafe': {'type': 'boolean'},
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
            self.url_match = re.compile(
                fr'^{escaped_url_scheme}://{escaped_url_netloc}/view/[^/]+/([a-zA-Z0-9]{24})$'
            )
            self.url_search = re.compile(
                fr'^{escaped_url_scheme}://{escaped_url_netloc}/search\?q=.*$'
            )

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.endswith('.torrent'):
            return False
        return bool(self.url_match.match(url))

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
            torrent_id = self.url_match(entry['url']).group(1)
            url = f"{self.url}/api/v1/torrents/{torrent_id}"
            logger.debug('Getting info for torrent ID {}', torrent_id)
            json_result = task.requests.get(url).json()
            # if json_result['error'] == '404':
            if not 'result' in json_result:
                raise UrlRewritingError("Torrent with ID %s does not exist." % torrent_id)
            entry['url'] = json_result['result']['rating']['magnet']

    @plugin.internet(logger)
    def search(self, task, entry, config=None):
        """
        Search for name from solidtorrents.
        """
        if not isinstance(config, dict):
            config = {}
        self.set_urls(config.get('url', URL))
        sort = config.get('sort_by', 'seeders')
        reverse = bool(config.get('reverse', 'False'))
        remove_potentially_unsafe = bool(config.get('remove_potentially_unsafe', 'True'))
        category = config.get('category', 'all')

        entries = list()
        for search_string in entry.get('search_strings', [entry['title']]):
            # query = normalize_unicode(search_string)
            params = {
                'q': search_string,
                'cat': category,
                'sort': sort,
                'fuv': remove_potentially_unsafe,
            }
            url = f"{self.url}/api/v1/search"
            json_results = task.requests.get(url, params=params).json()
            if not json_results:
                raise plugin.PluginError(
                    "Error while searching solidtorrents for %s.", search_string
                )
            if not 'results' in json_results:
                logger.info(
                    "No result founds while searching solidtorrents for %s.", search_string
                )
                continue
            for result in json_results['results']:
                entry = self.json_to_entry(result)
                entries.append(entry)

        return reversed(entries) if reverse else entries

    # convert a single json result to an Entry
    def json_to_entry(self, json_result: dict) -> Entry:
        entry = Entry()
        entry['title'] = json_result['title']
        entry['torrent_seeds'] = int(json_result['swarm']['seeders'])
        entry['torrent_leeches'] = int(json_result['swarm']['leechers'])
        entry['torrent_timestamp'] = int(
            time.mktime(
                datetime.strptime(json_result['imported'], '%Y-%m-%dT%H:%M:%S.%fZ').timetuple()
            )
        )
        entry['torrent_availability'] = torrent_availability(
            entry['torrent_seeds'], entry['torrent_leeches']
        )
        entry['content_size'] = int(
            round(int(json_result['size']) / (1024 * 1024))
        )  # content_size is in MiB
        entry['torrent_info_hash'] = json_result['infohash']
        entry['url'] = json_result['magnet']
        return entry


@event('plugin.register')
def register_plugin():
    plugin.register(
        UrlRewriteSolidTorrents,
        'solidtorrents',
        interfaces=['urlrewriter', 'search', 'task'],
        api_ver=2,
    )
