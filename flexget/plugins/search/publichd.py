from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves import urllib

import logging
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode

log = logging.getLogger('publichd')

CATEGORIES = {
    'all': 0,

    # Movies
    'BluRay 720p': 2,
    'BluRay 1080p': 5,
    'XviD': 15,
    'BRRip': 16,

    # TV
    'HDTV': 7,
    'SDTV': 24,
    'TV WEB-DL': 14
}


class SearchPublicHD(object):
    """
        PublicHD search plugin.

        To perform search against single category:

        publichd:
            category: BluRay 720p

        To perform search against multiple categories:

        publichd:
            category:
                - BluRay 720p
                - BluRay 1080p

        Movie categories accepted: BluRay 720p, BluRay 1080p, XviD, BRRip
        TV categories accepted: HDTV, SDTV, TV WEB-DL

        You can use also use category ID manually if you so desire (eg. BluRay 720p is actually category id '2')
    """

    schema = {
        'type': 'object',
        'properties': {
            'category': one_or_more({
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'string', 'enum': list(CATEGORIES)},
                ]})
        },
        "additionalProperties": False
    }

    @plugin.internet(log)
    def search(self, task, entry, config=None):
        """
            Search for entries on PublicHD
        """

        categories = config.get('category', 'all')
        # Ensure categories a list
        if not isinstance(categories, list):
            categories = [categories]
        # Convert named category to its respective category id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
        category_url_fragment = '&category=%s' % urllib.parse.quote(';'.join(str(c) for c in categories))

        base_url = 'http://publichd.se/index.php?page=torrents&active=0'

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)
            query_url_fragment = '&search=' + urllib.parse.quote(query.encode('utf8'))

            # http://publichd.se/index.php?page=torrents&active=0&category=5;15&search=QUERY
            url = (base_url + category_url_fragment + query_url_fragment)
            log.debug('PublicHD search url: %s' % url)

            page = requests.get(url).content
            soup = get_soup(page)

            for result in soup.findAll('a', href=re.compile('page=torrent-details')):
                entry = Entry()
                entry['title'] = result.text
                # Expand the selection to whole row
                result = result.findPrevious('tr')
                download_url = result.find('a', href=re.compile('\.torrent$'))['href']
                torrent_hash = re.search(r'/([0-9a-fA-F]{5,40})/', download_url).group(1)

                entry['url'] = 'http://publichd.se/download.php?id=%s' % torrent_hash

                seeds, leeches = result.findAll('td', text=re.compile('^\d+$'))
                entry['torrent_seeds'] = int(seeds.text)
                entry['torrent_leeches'] = int(leeches.text)
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                size = result.find("td", text=re.compile('(\d+(?:[.,]\d+)*)\s?([KMG]B)')).text
                size = re.search('(\d+(?:[.,]\d+)*)\s?([KMG]B)', size)

                if size:
                    if size.group(2) == 'GB':
                        entry['content_size'] = int(float(size.group(1).replace(',', '')) * 1000 ** 3 / 1024 ** 2)
                    elif size.group(2) == 'MB':
                        entry['content_size'] = int(float(size.group(1).replace(',', '')) * 1000 ** 2 / 1024 ** 2)
                    elif size.group(2) == 'KB':
                        entry['content_size'] = int(float(size.group(1).replace(',', '')) * 1000 / 1024 ** 2)
                    else:
                        entry['content_size'] = int(float(size.group(1).replace(',', '')) / 1024 ** 2)

                entries.add(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchPublicHD, 'publichd', groups=['search'], api_ver=2)
