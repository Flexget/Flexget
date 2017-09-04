from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import re
import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode
from flexget.utils.tools import parse_filesize

log = logging.getLogger('piratebay')

CUR_TLD = 'se'
TLDS = 'com|org|sx|ac|pe|gy|to|se|gd|vg|%s' % CUR_TLD

URL_MATCH = re.compile('^http://(?:torrents\.)?thepiratebay\.(?:%s)/.*$' % TLDS)
URL_SEARCH = re.compile('^http://thepiratebay\.(?:%s)/search/.*$' % TLDS)

CATEGORIES = {
    'all': 0,
    'audio': 100,
    'music': 101,
    'video': 200,
    'movies': 201,
    'tv': 205,
    'highres movies': 207,
    'highres tv': 208,
    'comics': 602
}

SORT = {
    'default': 99,  # This is piratebay default, not flexget default.
    'date': 3,
    'size': 5,
    'seeds': 7,
    'leechers': 9
}


class UrlRewritePirateBay(object):
    """PirateBay urlrewriter."""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'category': {
                        'oneOf': [
                            {'type': 'string', 'enum': list(CATEGORIES)},
                            {'type': 'integer'}
                        ]
                    },
                    'sort_by': {'type': 'string', 'enum': list(SORT)},
                    'sort_reverse': {'type': 'boolean'}
                },
                'additionalProperties': False
            }
        ]
    }

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.endswith('.torrent'):
            return False
        return bool(URL_MATCH.match(url))

    # urlrewriter API
    def url_rewrite(self, task, entry):
        if 'url' not in entry:
            log.error("Didn't actually get a URL...")
        else:
            log.debug("Got the URL: %s" % entry['url'])
        if URL_SEARCH.match(entry['url']):
            # use search
            results = self.search(task, entry)
            if not results:
                raise UrlRewritingError("No search results found")
            # TODO: Close matching was taken out of search methods, this may need to be fixed to be more picky
            entry['url'] = results[0]['url']
        else:
            # parse download page
            entry['url'] = self.parse_download_page(entry['url'], task.requests)

    @plugin.internet(log)
    def parse_download_page(self, url, requests):
        page = requests.get(url).content
        try:
            soup = get_soup(page)
            tag_div = soup.find('div', attrs={'class': 'download'})
            if not tag_div:
                raise UrlRewritingError('Unable to locate download link from url %s' % url)
            tag_a = tag_div.find('a')
            torrent_url = tag_a.get('href')
            # URL is sometimes missing the schema
            if torrent_url.startswith('//'):
                torrent_url = 'http:' + torrent_url
            return torrent_url
        except Exception as e:
            raise UrlRewritingError(e)

    @plugin.internet(log)
    def search(self, task, entry, config=None):
        """
        Search for name from piratebay.
        """
        if not isinstance(config, dict):
            config = {}
        sort = SORT.get(config.get('sort_by', 'seeds'))
        if config.get('sort_reverse'):
            sort += 1
        if isinstance(config.get('category'), int):
            category = config['category']
        else:
            category = CATEGORIES.get(config.get('category', 'all'))
        filter_url = '/0/%d/%d' % (sort, category)

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)

            # TPB search doesn't like dashes or quotes
            query = query.replace('-', ' ').replace("'", " ")

            # urllib.quote will crash if the unicode string has non ascii characters, so encode in utf-8 beforehand
            url = 'http://thepiratebay.%s/search/%s%s' % (CUR_TLD, quote(query.encode('utf-8')), filter_url)
            log.debug('Using %s as piratebay search url' % url)
            page = task.requests.get(url).content
            soup = get_soup(page)
            for link in soup.find_all('a', attrs={'class': 'detLink'}):
                entry = Entry()
                entry['title'] = self.extract_title(link)
                if not entry['title']:
                    log.error('Malformed search result. No title or url found. Skipping.')
                    continue
                entry['url'] = 'http://thepiratebay.%s%s' % (CUR_TLD, link.get('href'))
                tds = link.parent.parent.parent.find_all('td')
                entry['torrent_seeds'] = int(tds[-2].contents[0])
                entry['torrent_leeches'] = int(tds[-1].contents[0])
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                # Parse content_size
                size_text = link.find_next(attrs={'class': 'detDesc'}).get_text()
                if size_text:
                    size = re.search('Size (\d+(\.\d+)?\xa0(?:[PTGMK])?i?B)', size_text)
                    if size:
                        entry['content_size'] = parse_filesize(size.group(1))
                    else:
                        log.error('Malformed search result? Title: "%s", No size? %s', entry['title'], size_text)

                entries.add(entry)

        return sorted(entries, reverse=True, key=lambda x: x.get('search_sort'))

    @staticmethod
    def extract_title(soup):
        """Sometimes search results have no contents. This function tries to extract something sensible."""
        if isinstance(soup.contents, list) and soup.contents:
            return soup.contents[0]
        if soup.get('href') and 'torrent' in soup.get('href'):
            return soup.get('href').rsplit('/', 1)[-1]


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewritePirateBay, 'piratebay', interfaces=['urlrewriter', 'search'], api_ver=2)
