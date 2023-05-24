import re

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.components.sites.utils import normalize_unicode, torrent_availability
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='iptorrents')

CATEGORIES = {
    # All
    'All': '',
    # Movies
    'Movie-all': 72,
    'Movie-3D': 87,
    'Movie-480p': 77,
    'Movie-4K': 101,
    'Movie-BD-R': 89,
    'Movie-BD-Rip': 90,
    'Movie-Cam': 96,
    'Movie-DVD-R': 6,
    'Movie-HD-Bluray': 48,
    'Movie-Kids': 54,
    'Movie-MP4': 62,
    'Movie-Non-English': 38,
    'Movie-Packs': 68,
    'Movie-Web-DL': 20,
    'Movie-x265': 100,
    'Movie-XviD': 7,
    # TV
    'TV-all': 73,
    'TV-Documentaries': 26,
    'TV-Sports': 55,
    'TV-480p': 78,
    'TV-BD': 23,
    'TV-DVD-R': 24,
    'TV-DVD-Rip': 25,
    'TV-Mobile': 66,
    'TV-Non-English': 82,
    'TV-Packs': 65,
    'TV-Packs-Non-English': 83,
    'TV-SD-x264': 79,
    'TV-x264': 5,
    'TV-x265': 99,
    'TV-XVID': 4,
    'TV-Web-DL': 22,
}

DOMAIN = "iptorrents.com"
BASE_URL = f"https://{DOMAIN}"
SEARCH_URL = f"https://{DOMAIN}/t?"
FREE_SEARCH_URL = f"https://{DOMAIN}/t?free=on"
DELAY = "2 seconds"


class UrlRewriteIPTorrents:
    """
    IpTorrents urlrewriter and search plugin.

    iptorrents:
      rss_key: xxxxxxxxx  (required)
      uid: xxxxxxxx  (required)
      password: xxxxxxxx  (required)
      category: HD
      free: False
      search_delay: "1 seconds"

      Category is any combination of: Movie-all, Movie-3D, Movie-480p,
      Movie-4K, Movie-BD-R, Movie-BD-Rip, Movie-Cam, Movie-DVD-R,
      Movie-HD-Bluray, Movie-Kids, Movie-MP4, Movie-Non-English,
      Movie-Packs, Movie-Web-DL, Movie-x265, Movie-XviD,
      TV-all, TV-Documentaries, TV-Sports, TV-480p, TV-BD, TV-DVD-R,
      TV-DVD-Rip, TV-MP4, TV-Mobile, TV-Non-English, TV-Packs,
      TV-Packs-Non-English, TV-SD-x264, TV-x264, TV-x265, TV-XVID, TV-Web-DL

      free is a boolean to control search result filtering for freeleach torrents only.

      search_delay is a timedelta string that configures rate limit for requests to iptorrents.com.
    """

    schema = {
        'type': 'object',
        'properties': {
            'rss_key': {'type': 'string'},
            'uid': {'oneOf': [{'type': 'integer'}, {'type': 'string'}]},
            'password': {'type': 'string'},
            'category': one_or_more(
                {'oneOf': [{'type': 'integer'}, {'type': 'string', 'enum': list(CATEGORIES)}]}
            ),
            'free': {'type': 'boolean', 'default': False},
        },
        'required': ['rss_key', 'uid', 'password'],
        'additionalProperties': False,
    }

    # urlrewriter API
    def url_rewritable(self, task, entry):
        """
        Determines if the entry's URL is rewriteable (not pointing at a downloadable torrent).
        """
        url = entry['url']
        if url.startswith(BASE_URL + '/download.php/'):
            return False
        if url.startswith(BASE_URL + '/'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        """
        Resets the entry's url to one pointing directly at a torrent.
        """
        if 'url' not in entry:
            logger.error("Didn't actually get a URL...")
        else:
            logger.debug('Got the URL: {}', entry['url'])
        if entry['url'].startswith(SEARCH_URL):
            # use search
            results = self.search(task, entry)
            if not results:
                raise UrlRewritingError("No search results found")
            # TODO: Search doesn't enforce close match to title, be more picky
            entry['url'] = results[0]['url']

    @plugin.internet(logger)
    def search(self, task, entry, config=None):
        """
        Search for name from iptorrents.
        """

        categories = config.get('category', 'All')
        # Make sure categories is a list
        if not isinstance(categories, list):
            categories = [categories]

        # If there are any text categories, turn them into their id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
        category_params = {str(c): '' for c in categories if str(c)}

        entries = set()

        if not task.requests.domain_limiters.get(DOMAIN, None):
            logger.debug('limiting requests with a delay of {}', DELAY)
            rate_limiter = requests.TokenBucketLimiter(DOMAIN, 1, DELAY, True)
            task.requests.add_domain_limiter(rate_limiter)

        for search_string in entry.get('search_strings', [entry['title']]):
            search_params = dict(category_params.items())

            query = normalize_unicode(search_string)
            search_params.update({'q': query, 'qf': ''})

            logger.debug('searching with params: {}', search_params)
            if config.get('free'):
                req = task.requests.get(
                    FREE_SEARCH_URL,
                    params=search_params,
                    cookies={'uid': str(config['uid']), 'pass': config['password']},
                )
            else:
                req = task.requests.get(
                    SEARCH_URL,
                    params=search_params,
                    cookies={'uid': str(config['uid']), 'pass': config['password']},
                )
            logger.debug('full search URL: {}', req.url)

            if '/u/' + str(config['uid']) not in req.text:
                raise plugin.PluginError("Invalid cookies (user not logged in)...")

            soup = get_soup(req.content, parser='html5lib')
            torrents = soup.find('table', {'id': 'torrents'})
            seeders_idx = None
            leechers_idx = None
            for idx, header in enumerate(torrents.thead.find('tr').findAll('th', recursive=False)):
                header_text = header.text
                if 'seeders' in header_text:
                    seeders_idx = idx
                if 'leechers' in header_text:
                    leechers_idx = idx

            for torrent in torrents.tbody.findAll('tr', recursive=False):
                if torrent.th and 'ac' in torrent.th.get('class'):
                    # Header column
                    continue
                cols = list(torrent.findAll('td', recursive=False))
                if len(cols) == 1 and 'No Torrents Found' in cols[0].text:
                    logger.debug('No results found for search {}', search_string)
                    break
                entry = Entry()
                link = torrent.find('a', href=re.compile('download'))['href']
                entry['url'] = f"{BASE_URL}{link}?torrent_pass={config.get('rss_key')}"
                entry['title'] = torrent.find('a', href=re.compile('details|/t/[0-9]+$')).text

                seeders = cols[seeders_idx].text
                leechers = cols[leechers_idx].text
                entry['torrent_seeds'] = int(seeders)
                entry['torrent_leeches'] = int(leechers)
                entry['torrent_availability'] = torrent_availability(
                    entry['torrent_seeds'], entry['torrent_leeches']
                )

                size = torrent.findNext(text=re.compile(r'^([\.\d]+) ([GMK]?)B$'))
                size = re.search(r'^([\.\d]+) ([GMK]?)B$', size)

                entry['content_size'] = parse_filesize(size.group(0))
                logger.debug('Found entry {}', entry)
                entries.add(entry)

        return entries


@event('plugin.register')
def register_plugin():
    """
    Registers the plugin with FlexGet's plugin system.
    """
    plugin.register(
        UrlRewriteIPTorrents, 'iptorrents', interfaces=['urlrewriter', 'search'], api_ver=2
    )
