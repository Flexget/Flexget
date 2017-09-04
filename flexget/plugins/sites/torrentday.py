from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import re
import logging

from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.plugins.internal.urlrewriting import UrlRewritingError
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode
from flexget.utils.tools import parse_filesize

log = logging.getLogger('torrentday')

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
    'tvXVID': 2
}


class UrlRewriteTorrentday(object):
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
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'string', 'enum': list(CATEGORIES)},
                ]
            },
        },
        'required': ['rss_key', 'uid', 'passkey', 'cfduid'],
        'additionalProperties': False
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
            log.error('Didn\'t actually get a URL...')
        else:
            log.debug('Got the URL: %s', entry['url'])
        if entry['url'].startswith('https://www.torrentday.com/browse'):
            # use search
            results = self.search(task, entry)
            if not results:
                raise UrlRewritingError('No search results found')
            entry['url'] = results[0]['url']

    @plugin.internet(log)
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
        params = { 'cata': 'yes', 'c%s' % ','.join(str(c) for c in categories): 1, 'clear-new': 1}
        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):

            url = 'https://www.torrentday.com/browse.php'
            params['search'] = normalize_unicode(search_string).replace(':', '')
            cookies = { 'uid': config['uid'], 'pass': config['passkey'], '__cfduid': config['cfduid'] }

            try:
                page = requests.get(url, params=params, cookies=cookies).content
            except RequestException as e:
                raise PluginError('Could not connect to torrentday: %s' % e)

            soup = get_soup(page)

            for tr in soup.find_all('tr', { 'class': 'browse' }):
                entry = Entry()
                # find the torrent names
                title = tr.find('a', { 'class': 'torrentName' })
                entry['title'] = title.contents[0]
                log.debug('title: %s', title.contents[0])

                # find download link
                torrent_url = tr.find('td', { 'class': 'dlLinksInfo' })
                torrent_url = torrent_url.find('a').get('href')

                # construct download URL
                torrent_url = ( 'https://www.torrentday.com/' + torrent_url + '?torrent_pass=' + config['rss_key'] )
                log.debug('RSS-ified download link: %s', torrent_url)
                entry['url'] = torrent_url

                # us tr object for seeders/leechers
                seeders, leechers = tr.find_all('td', { 'class': ['seedersInfo', 'leechersInfo']})
                entry['torrent_seeds'] = int(seeders.contents[0].replace(',', ''))
                entry['torrent_leeches'] = int(leechers.contents[0].replace(',', ''))
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])

                # use tr object for size
                size = tr.find('td', text=re.compile('([\.\d]+) ([TGMKk]?)B')).contents[0]
                size = re.search('([\.\d]+) ([TGMKk]?)B', str(size))

                entry['content_size'] = parse_filesize(size.group(0))

                entries.add(entry)

        return sorted(entries, reverse=True, key=lambda x: x.get('search_sort'))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteTorrentday, 'torrentday', interfaces=['urlrewriter', 'search'], api_ver=2)
