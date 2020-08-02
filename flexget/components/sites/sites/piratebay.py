import re
from urllib.parse import quote, urlparse

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.components.sites.utils import normalize_unicode, torrent_availability
from flexget.entry import Entry
from flexget.event import event

from flexget.utils.tools import parse_filesize

import json
from urllib.parse import urlparse, parse_qs, urlencode

logger = logger.bind(name='piratebay')

URL = 'https://apibay.org' # for TOR: http://piratebayztemzmv.onion

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
            # most api mirrors share the same domain with frontend, except thepiratebay.org which uses apibay.org
            self.url_match = re.compile(
                r'^%s://(?:[a-z0-9]+\.)?(?:thepiratebay\.org(?:\:\d+)?|%s)/description\.php\?id=(\d+)$'
                % (re.escape(parsed_url.scheme), re.escape(parsed_url.netloc))
            )
            self.url_search = re.compile(r'^(?:thepiratebay\.org(?:\:\d+)?|%s)/search\.php\?q=.*$' % (re.escape(url)))

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
            torrent_id = self.url_match.match(entry['url']).group(1)
            url = '%s/t.php?id=%s' % (self.url, torrent_id)
            logger.debug('Getting info for torrent ID {}', torrent_id)
            page = task.requests.get(url).content
            json_result = json.loads(page)[0]
            if json_result['id'] == '0':
                raise UrlRewritingError("Torrent with ID does not exist.")
            else:
                entry['url'] = UrlRewritePirateBay.info_hash_to_magnet(json_result['info_hash'], json_result['name'])

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
        filter_url = '&cat=%s' % category

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)

            # TPB search doesn't like dashes or quotes
            # query = query.replace('-', ' ').replace("'", " ")

            # urllib.quote will crash if the unicode string has non ascii characters, so encode in utf-8 beforehand
            url = '%s/q.php?q=%s%s' % (self.url, quote(query.encode('utf-8')), filter_url)
            logger.debug('Using {} as piratebay search url', url)
            page = task.requests.get(url).content
            json_results = json.loads(page)
            if len(json_results) == 0:
                logger.error("Error while searching piratebay for %s." % search_string)
            for result in json_results:
                if result['id'] == '0':
                    # JSON when no results found:
                    # [{
                    #    "id":"0",
                    #    "name":"No results returned",
                    #    "info_hash":"0000000000000000000000000000000000000000",
                    #    "leechers":"0",
                    #    "seeders":"0",
                    #    "num_files":"0",
                    #    "size":"0",
                    #    "username":"",
                    #    "added":"0",
                    #    "status":"member",
                    #    "category":"0",
                    #    "imdb":"",
                    #    "total_found":"1"
                    # }]
                    break
                try:
                    entry = Entry()
                    entry['title'] = result['name']
                    entry['torrent_seeds'] = int(result['seeders'])
                    entry['torrent_leeches'] = int(result['leechers'])
                    entry['torrent_timestamp'] = int(result['added'])
                    entry['torrent_availability'] = torrent_availability(
                        entry['torrent_seeds'], entry['torrent_leeches']
                    )
                    entry['content_size'] = result['size']
                    entry['torrent_info_hash'] = result['info_hash']
                    entry['url'] = UrlRewritePirateBay.info_hash_to_magnet(result['info_hash'], result['name'])
                except KeyError:
                    logger.error("Error when parsing an entry.")

                entries.add(entry)

        return sorted(entries, reverse=sort_reverse, key=lambda x: x.get(sort))

    @staticmethod
    def info_hash_to_magnet(info_hash, name):
        magnet = {
            'xt': f"urn:btih:{info_hash}",
            'dn': name,
            'tr': TRACKERS
        }
        magnet_qs = urlencode(magnet, doseq=True, safe=':')
        magnet_uri = f"magnet:?{magnet_qs}"
        return magnet_uri

@event('plugin.register')
def register_plugin():
    plugin.register(
        UrlRewritePirateBay, 'piratebay', interfaces=['urlrewriter', 'search', 'task'], api_ver=2
    )

