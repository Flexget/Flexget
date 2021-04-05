from urllib.parse import quote

from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.components.sites.utils import normalize_unicode, torrent_availability
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='torrentleech')

CATEGORIES = {
    'all': 0,
    # Movies
    'Cam': 8,
    'TS': 9,
    'TS/TC': 9,
    'DVDRip/DVDScreener': 11,
    'WEBRip': 37,
    'HDRip': 43,
    'BlurayRip': 14,
    'DVD-R': 12,
    'Bluray': 13,
    '4KUpscaled': 41,
    'Real4K': 47,
    'Boxsets': 15,
    'Documentaries': 29,
    # TV
    'Episodes': 26,
    'TV Boxsets': 27,
    'Episodes HD': 32,
}


class UrlRewriteTorrentleech:
    """
    Torrentleech urlrewriter and search plugin.

    torrentleech:
      rss_key: xxxxxxxxx  (required)
      username: xxxxxxxx  (required)
      password: xxxxxxxx  (required)
      category: HD

      Category is any combination of: all, Cam, TS, TS/TC, DVDRip,
      DVDRip/DVDScreener, WEBRip': 37, HDRip': 43, BDRip, DVDR,
      DVD-R, HD, Bluray, 4KUpscaled, Real4K, Movie Boxsets,
      Boxsets': 15, Documentaries, Episodes, TV Boxsets, Episodes HD
    """

    schema = {
        'type': 'object',
        'properties': {
            'rss_key': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'category': one_or_more(
                {'oneOf': [{'type': 'integer'}, {'type': 'string', 'enum': list(CATEGORIES)}]}
            ),
        },
        'required': ['rss_key', 'username', 'password'],
        'additionalProperties': False,
    }

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.endswith('.torrent'):
            return False
        if url.startswith('https://www.torrentleech.org/'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        if 'url' not in entry:
            logger.error("Didn't actually get a URL...")
        else:
            logger.debug('Got the URL: {}', entry['url'])
        if entry['url'].startswith('https://www.torrentleech.org/torrents/browse/list/query/'):
            # use search
            results = self.search(task, entry)
            if not results:
                raise UrlRewritingError("No search results found")
            # TODO: Search doesn't enforce close match to title, be more picky
            entry['url'] = results[0]['url']

    @plugin.internet(logger)
    def search(self, task, entry, config=None):
        """
        Search for name from torrentleech.
        """
        request_headers = {'User-Agent': 'curl/7.54.0'}
        rss_key = config['rss_key']

        # build the form request:
        data = {'username': config['username'], 'password': config['password']}
        # POST the login form:
        try:
            login = task.requests.post(
                'https://www.torrentleech.org/user/account/login/',
                data=data,
                headers=request_headers,
                allow_redirects=True,
            )
        except RequestException as e:
            raise PluginError('Could not connect to torrentleech: %s' % str(e))

        if login.url.endswith('/user/account/login/'):
            raise PluginError('Could not login to torrentleech, faulty credentials?')

        if not isinstance(config, dict):
            config = {}
            # sort = SORT.get(config.get('sort_by', 'seeds'))
            # if config.get('sort_reverse'):
            # sort += 1
        categories = config.get('category', 'all')
        # Make sure categories is a list
        if not isinstance(categories, list):
            categories = [categories]
        # If there are any text categories, turn them into their id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
        filter_url = '/categories/{}'.format(','.join(str(c) for c in categories))
        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string).replace(":", "")
            # urllib.quote will crash if the unicode string has non ascii characters,
            # so encode in utf-8 beforehand

            url = (
                'https://www.torrentleech.org/torrents/browse/list/query/'
                + quote(query.encode('utf-8'))
                + filter_url
            )
            logger.debug('Using {} as torrentleech search url', url)

            results = task.requests.get(url, headers=request_headers, cookies=login.cookies).json()

            for torrent in results['torrentList']:
                entry = Entry()
                entry['download_headers'] = request_headers
                entry['title'] = torrent['name']

                # construct download URL
                torrent_url = 'https://www.torrentleech.org/rss/download/{}/{}/{}'.format(
                    torrent['fid'], rss_key, torrent['filename']
                )
                logger.debug('RSS-ified download link: {}', torrent_url)
                entry['url'] = torrent_url

                # seeders/leechers
                entry['torrent_seeds'] = torrent['seeders']
                entry['torrent_leeches'] = torrent['leechers']
                entry['torrent_availability'] = torrent_availability(
                    entry['torrent_seeds'], entry['torrent_leeches']
                )
                entry['content_size'] = parse_filesize(str(torrent['size']) + ' b')
                entries.add(entry)

        return sorted(entries, reverse=True, key=lambda x: x.get('torrent_availability'))


@event('plugin.register')
def register_plugin():
    plugin.register(
        UrlRewriteTorrentleech, 'torrentleech', interfaces=['urlrewriter', 'search'], api_ver=2
    )
