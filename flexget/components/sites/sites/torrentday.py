import re

from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.components.sites.utils import normalize_unicode, torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='torrentday')

CATEGORIES = {
    'all': 0,
    # Movies
    'mov480p': 25,
    'movHD': 11,
    'movBD': 5,
    'movDVD': 3,
    'movMP4': 21,
    'movNonEnglish': 22,
    'movPACKS': 13,
    'movSDx264': 44,
    'movX265': 48,
    'movXVID': 1,
    # TV
    'tv480p': 24,
    'tvBRD': 32,
    'tvDVD': 31,
    'tvDVDrip': 33,
    'tvMOBILE': 46,
    'tvPACKS': 14,
    'tvSDx264': 26,
    'tvHDx264': 7,
    'tvX265': 34,
    'tvXVID': 2,
}


class UrlRewriteTorrentday:
    """
        Torrentday urlrewriter and search plugin.

        torrentday:
          uid: xxxxxxxxxxxxx  (required)    NOT YOUR LOGIN. find this in your browser's cookies
          passkey: xxxxxxxxx  (required)    NOT YOUR PASSWORD. see previous
          cfduid: xxxxxxxxxx  (required)    AGAIN IN THE COOKIES
          rss_key: xxxxxxxxx  (required)    get this from your profile page
          category: xxxxxxxx

          Category can be one of 
            ID from browsing site OR 'name'
            movies:
              mov480p, movHD, movBD, movDVD,
              movMP4, movNonEnglish, movPACKS,
              movSDx264, movX265, movXVID
            tv:
              tv480p, tvBRD, tvDVD, tvDVDrip,
              tvMOBILE, tvPACKS, tvSDx264, 
              tvHDx264, tvX265, tvXVID
    """

    schema = {
        'type': 'object',
        'properties': {
            'rss_key': {'type': 'string'},
            'uid': {'type': 'string'},
            'passkey': {'type': 'string'},
            'cfduid': {'type': 'string'},
            'category': {
                'oneOf': [{'type': 'integer'}, {'type': 'string', 'enum': list(CATEGORIES)}]
            },
        },
        'required': ['rss_key', 'uid', 'passkey', 'cfduid'],
        'additionalProperties': False,
    }

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.find('.torrent'):
            return False
        if url.startswith('https://www.torrentday.com'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        if 'url' not in entry:
            logger.error('Didn\'t actually get a URL...')
        else:
            logger.debug('Got the URL: {}', entry['url'])
        if entry['url'].startswith('https://www.torrentday.com/browse'):
            # use search
            results = self.search(task, entry)
            if not results:
                raise UrlRewritingError('No search results found')
            entry['url'] = results[0]['url']

    @plugin.internet(logger)
    def search(self, task, entry, config=None):
        """
        Search for name from torrentday.
        """

        categories = config.get('category', 'all')
        # Make sure categories is a list
        if not isinstance(categories, list):
            categories = [categories]
        # If there are any text categories, turn them into their id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
        params = {
            'cata': 'yes',
            'c{}'.format(','.join(str(c) for c in categories)): 1,
            'clear-new': 1,
        }
        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):

            url = 'https://www.torrentday.com/t'
            params['q'] = normalize_unicode(search_string).replace(':', '')
            cookies = {
                'uid': config['uid'],
                'pass': config['passkey'],
                '__cfduid': config['cfduid'],
            }

            try:
                page = requests.get(url, params=params, cookies=cookies).content
            except RequestException as e:
                raise PluginError('Could not connect to torrentday: {}'.format(e))

            # the following should avoid table being None due to a malformed
            # html in td search results
            soup = get_soup(page).contents[1].contents[1].next.next.nextSibling
            table = soup.find('table', {'id': 'torrentTable'})
            if table is None:
                raise PluginError(
                    'Search returned by torrentday appears to be empty or malformed.'
                )

            # the first row is the header so skip it
            for tr in table.find_all('tr')[1:]:
                entry = Entry()
                # find the torrent names
                td = tr.find('td', {'class': 'torrentNameInfo'})
                if not td:
                    logger.warning('Could not find entry torrentNameInfo for {}.', search_string)
                    continue
                title = td.find('a')
                if not title:
                    logger.warning('Could not determine title for {}.', search_string)
                    continue
                entry['title'] = title.contents[0]
                logger.debug('title: {}', title.contents[0])

                # find download link
                torrent_url = tr.find('td', {'class': 'ac'})
                if not torrent_url:
                    logger.warning('Could not determine download link for {}.', search_string)
                    continue
                torrent_url = torrent_url.find('a').get('href')

                # construct download URL
                torrent_url = (
                    'https://www.torrentday.com/'
                    + torrent_url
                    + '?torrent_pass='
                    + config['rss_key']
                )
                logger.debug('RSS-ified download link: {}', torrent_url)
                entry['url'] = torrent_url

                # us tr object for seeders/leechers
                seeders = tr.find('td', {'class': 'ac seedersInfo'})
                leechers = tr.find('td', {'class': 'ac leechersInfo'})
                entry['torrent_seeds'] = int(seeders.contents[0].replace(',', ''))
                entry['torrent_leeches'] = int(leechers.contents[0].replace(',', ''))
                entry['torrent_availability'] = torrent_availability(
                    entry['torrent_seeds'], entry['torrent_leeches']
                )

                # use tr object for size
                size = tr.find('td', text=re.compile(r'([\.\d]+) ([TGMKk]?)B')).contents[0]
                size = re.search(r'([\.\d]+) ([TGMKk]?)B', str(size))

                entry['content_size'] = parse_filesize(size.group(0))

                entries.add(entry)

        return sorted(entries, reverse=True, key=lambda x: x.get('torrent_availability'))


@event('plugin.register')
def register_plugin():
    plugin.register(
        UrlRewriteTorrentday, 'torrentday', interfaces=['urlrewriter', 'search'], api_ver=2
    )
