from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
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

log = logging.getLogger('torrentleech')

CATEGORIES = {
    'all': 0,

    # Movies
    'Cam': 8,
    'TS': 9,
    'R5': 10,
    'DVDRip': 11,
    'DVDR': 12,
    'HD': 13,
    'BDRip': 14,
    'Movie Boxsets': 15,
    'Documentaries': 29,

    # TV
    'Episodes': 26,
    'TV Boxsets': 27,
    'Episodes HD': 32
}


class UrlRewriteTorrentleech(object):
    """
        Torrentleech urlrewriter and search plugin.

        torrentleech:
          rss_key: xxxxxxxxx  (required)
          username: xxxxxxxx  (required)
          password: xxxxxxxx  (required)
          category: HD

          Category is any combination of: all, Cam, TS, R5,
          DVDRip, DVDR, HD, BDRip, Movie Boxsets, Documentaries,
          Episodes, TV BoxSets, Episodes HD
    """

    schema = {
        'type': 'object',
        'properties': {
            'rss_key': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'category': one_or_more({
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'string', 'enum': list(CATEGORIES)},
                ]
            }),
        },
        'required': ['rss_key', 'username', 'password'],
        'additionalProperties': False
    }

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.endswith('.torrent'):
            return False
        if url.startswith('http://torrentleech.org/'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        if 'url' not in entry:
            log.error("Didn't actually get a URL...")
        else:
            log.debug("Got the URL: %s" % entry['url'])
        if entry['url'].startswith('http://torrentleech.org/torrents/browse/index/query/'):
            # use search
            results = self.search(task, entry)
            if not results:
                raise UrlRewritingError("No search results found")
            # TODO: Search doesn't enforce close match to title, be more picky
            entry['url'] = results[0]['url']

    @plugin.internet(log)
    def search(self, task, entry, config=None):
        """
        Search for name from torrentleech.
        """
        rss_key = config['rss_key']

        # build the form request:
        data = {'username': config['username'], 'password': config['password'], 'remember_me': 'on', 'submit': 'submit'}
        # POST the login form:
        try:
            login = requests.post('https://torrentleech.org/', data=data)
        except RequestException as e:
            raise PluginError('Could not connect to torrentleech: %s', str(e))

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
        filter_url = '/categories/%s' % ','.join(str(c) for c in categories)
        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string).replace(":", "")
            # urllib.quote will crash if the unicode string has non ascii characters, so encode in utf-8 beforehand
            url = ('http://torrentleech.org/torrents/browse/index/query/' +
                   quote(query.encode('utf-8')) + filter_url)
            log.debug('Using %s as torrentleech search url' % url)

            page = requests.get(url, cookies=login.cookies).content
            soup = get_soup(page)

            for tr in soup.find_all("tr", ["even", "odd"]):
                # within each even or odd row, find the torrent names
                link = tr.find("a", attrs={'href': re.compile('/torrent/\d+')})
                log.debug('link phase: %s' % link.contents[0])
                entry = Entry()
                # extracts the contents of the <a>titlename/<a> tag
                entry['title'] = link.contents[0]

                # find download link
                torrent_url = tr.find("a", attrs={'href': re.compile('/download/\d+/.*')}).get('href')
                # parse link and split along /download/12345 and /name.torrent
                download_url = re.search('(/download/\d+)/(.+\.torrent)', torrent_url)
                # change link to rss and splice in rss_key
                torrent_url = 'http://torrentleech.org/rss' + download_url.group(1) + '/' \
                              + rss_key + '/' + download_url.group(2)
                log.debug('RSS-ified download link: %s' % torrent_url)
                entry['url'] = torrent_url

                # us tr object for seeders/leechers
                seeders, leechers = tr.find_all('td', ["seeders", "leechers"])
                entry['torrent_seeds'] = int(seeders.contents[0])
                entry['torrent_leeches'] = int(leechers.contents[0])
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])

                # use tr object for size
                size = tr.find("td", text=re.compile('([\.\d]+) ([TGMK]?)B')).contents[0]
                size = re.search('([\.\d]+) ([TGMK]?)B', size)

                entry['content_size'] = parse_filesize(size.group(0))

                entries.add(entry)

        return sorted(entries, reverse=True, key=lambda x: x.get('search_sort'))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteTorrentleech, 'torrentleech', groups=['urlrewriter', 'search'], api_ver=2)
