from __future__ import unicode_literals, division, absolute_import
import re
import urllib
import logging


from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode

log = logging.getLogger('iptorrents')

CATEGORIES = {

    'Movie-all': 72,

    # Movies
    'Movie-3D': 87,
    'Movie-480p': 77,
    'Movie-BD-R': 89,
    'Movie-BD-Rip': 90,
    'Movie-DVD-R': 6,
    'Movie-HD-Bluray': 48,
    'Movie-Kids': 54,
    'Movie-MP4': 62,
    'Movie-Non-English': 38,
    'Movie-Packs': 68,
    'Movie-XviD': 17,

    #TV
    'TV-all': 73,

    'TV-Sports': 55,
    'TV-480p': 78,
    'TV-MP4': 66,
    'TV-Non-English': 82,
    'TV-Packs': 65,
    'TV-Packs-Non-English': 83,
    'TV-SD-x264': 79,
    'TV-x264': 5,
    'TV-XVID': 4
}
import sys


class UrlRewriteIPTorrents(object):
    """
        IpTorrents urlrewriter and search plugin.

        iptorrents:
          rss_key: xxxxxxxxx  (required)
          uid: xxxxxxxx  (required)
          password: xxxxxxxx  (required)
          category: HD

          Category is any combination of: all, Movie-3D, Movie-480p, Movie-3D,
                Movie-480p, Movie-BD-R, Movie-BD-Rip, Movie-DVD-R,
                Movie-HD-Bluray, Movie-Kids, Movie-MP4,
                Movie-Non-English, Movie-Packs, Movie-XviD,

                TV-all, TV-Sports, TV-480p, TV-MP4, TV-Non-English, TV-Packs,
                TV-Packs-Non-English, TV-SD-x264, TV-x264,	TV-XVID
    """

    schema = {
        'type': 'object',
        'properties': {
            'rss_key': {'type': 'string'},
            'uid': {'type': 'integer'},
            'password': {'type': 'string'},
            'category': one_or_more({
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'string', 'enum': list(CATEGORIES)},
                ]}),
        },
        'required': ['rss_key', 'uid', 'password'],
        'additionalProperties': False
    }

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('http://iptorrents.com/download.php/'):
            return False
        if url.startswith('http://iptorrents.com/'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        if not 'url' in entry:
            log.error("Didn't actually get a URL...")
        else:
            log.debug("Got the URL: %s" % entry['url'])
        if entry['url'].startswith('http://iptorrents.com/t?'):
            # use search
            results = self.search(entry)
            if not results:
                raise UrlRewritingError("No search results found")
            # TODO: Search doesn't enforce close match to title, be more picky
            entry['url'] = results[0]['url']

    @plugin.internet(log)
    def search(self, entry, config=None):
        """
        Search for name from torrentleech.
        """
        rss_key = config['rss_key']

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
        categories = [c if isinstance(c, int) else CATEGORIES[c]
                      for c in categories]
        filter_url = '&'.join(('l' + str(c) + '=') for c in categories)

        entries = set()

        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)

            # urllib.quote will crash if the unicode string has non ascii
            # characters, so encode in utf-8 beforehand
            url = ('http://iptorrents.com/t?' + filter_url + '&q=' +
                   urllib.quote_plus(query.encode('utf-8')) + '&qf=')

            page = requests.get(url, cookies={'uid': str(config['uid']),
                                'pass': config['password']}).content
            soup = get_soup(page)

            if soup.find("title").contents[0] == "IPT":
                raise plugin.PluginError("Page title unexpected: Could it be the login page?...")

            log.debug('searching with url: %s' % url)

            tb = soup.find('table', {'class': 'torrents'})
            if not tb:
                continue

            # list all row of torrents table except first because it is titles
            for tr in tb.findAll('tr')[1:]:

                h1 = tr.find('h1')
                if h1 is not None:
                    if h1.contents[0] == 'No Torrents Found!':
                        break

                link = tr.find("a", attrs={'href':
                                           re.compile('/details\.php\?id=\d+')
                                           })
                log.debug('link phase: %s' % link.contents[0])

                entry = Entry()
                entry['title'] = link.contents[0]

                torrent_url = tr.find("a", attrs={'href': re.compile('/download.php/\d+/.*')}).get('href')
                torrent_url = normalize_unicode(torrent_url)
                torrent_url = urllib.quote(torrent_url.encode('utf-8'))
                torrent_url = 'http://iptorrents.com' + torrent_url + '?torrent_pass=' + rss_key

                log.debug('RSS-ified download link: %s' % torrent_url)

                entry['url'] = torrent_url

                seeders = tr.find_all('td', {'class': 'ac t_seeders'})
                leechers = tr.find_all('td', {'class': 'ac t_leechers'})
                entry['torrent_seeds'] = int(seeders[0].contents[0])
                entry['torrent_leeches'] = int(leechers[0].contents[0])
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'],
                                                            entry['torrent_leeches'])
                size = tr.find("td", text=re.compile('([\.\d]+) ([GMK]?)B')).contents[0]

                size = re.search('([\.\d]+) ([GMK]?)B', size)
                if size:
                    if size.group(2) == 'G':
                        entry['content_size'] = int(float(size.group(1)) * 1000 ** 3 / 1024 ** 2)
                    elif size.group(2) == 'M':
                        entry['content_size'] = int(float(size.group(1)) * 1000 ** 2 / 1024 ** 2)
                    elif size.group(2) == 'K':
                        entry['content_size'] = int(float(size.group(1)) * 1000 / 1024 ** 2)
                    else:
                        entry['content_size'] = int(float(size.group(1)) / 1024 ** 2)
                entries.add(entry)

        return sorted(entries, reverse=True, key=lambda x: x.get('search_sort'))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteIPTorrents, 'iptorrents',
                    groups=['urlrewriter', 'search'], api_ver=2)
