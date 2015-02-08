from __future__ import unicode_literals, division, absolute_import
import logging
import urllib
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils import requests
from flexget.utils.requests import Session
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode

log = logging.getLogger('rarbg')

session = Session()

CATEGORIES = {
    'all': 0,

    # Movies
    'x264 720p': 45,
    'x264 1080p': 44,
    'XviD': 14,
    'Full BD': 42,

    # TV
    'HDTV': 41,
    'SDTV': 18
}


class SearchRarBG(object):
    """
        RarBG search plugin.

        To perform search against single category:

        rarbg:
            category: x264 720p

        To perform search against multiple categories:

        publichd:
            category:
                - x264 720p
                - x264 1080p

        Movie categories accepted: x264 720p, x264 1080p, XviD, Full BD
        TV categories accepted: HDTV, SDTV

        You can use also use category ID manually if you so desire (eg. x264 720p is actually category id '45')
    """

    schema = {
        'type': 'object',
        'properties': {
            'category': one_or_more({
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'string', 'enum': list(CATEGORIES)},
                ]}),
            'cookies': {'type': 'string'}
        },
        "additionalProperties": False
    }

    base_url = 'http://rarbg.com'

    def rewrite(self, entry, task=None, cookies=None, **kwargs):
        url = entry['url']

        log.info('RarBG rewriting download url: %s' % url)

        page = session.get(url, cookies=cookies).content
        soup = get_soup(page)

        entry['url'] = self.base_url + soup.find('a', href=re.compile('\.torrent$'))['href']

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for entries on RarBG
        """

        categories = config.get('category', 'all')
        # Ensure categories a list
        if not isinstance(categories, list):
            categories = [categories]
        # Convert named category to its respective category id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
        category_url_fragment = '&category=%s' % urllib.quote(';'.join(str(c) for c in categories))

        base_search_url = self.base_url + '/torrents.php?order=seeders&by=ASC'

        cookies = config.get('cookies', {'7fAY799j': 'VtdTzG69'})
        if not isinstance(cookies, dict):
            cookies = cookies.split(':')
            cookies = {cookies[0]: cookies[1]}

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)
            query_url_fragment = '&search=' + urllib.quote(query.encode('utf8'))

            # http://rarbg.com/torrents.php?order=seeders&by=DESC&category=41;18&search=QUERY
            url = (base_search_url + category_url_fragment + query_url_fragment)
            log.debug('RarBG search url: %s' % url)

            page = requests.get(url, cookies=cookies).content

            soup = get_soup(page)

            if soup.find(text='Bot check !'):
                log.error('RarBG search failed. Caught by bot detection. Please check your cookies.')
                break

            for result in soup.findAll('tr', class_='lista2'):
                if not result.find('a', href=re.compile('/torrent/')):
                    continue

                entry = Entry()

                entry['title'] = result.find('a', href=re.compile('/torrent/')).text
                download_url = self.base_url + result.find('a', href=re.compile('/torrent/'))['href']

                entry['url'] = download_url

                tds = result.findAll('td')
                seeds = tds[4]
                leeches = tds[5]
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
                # use the rewrite function to rewrite accepted entry urls to avoid hammering rarbg
                entry.on_accept(self.rewrite, cookies=cookies)
                entries.add(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchRarBG, 'rarbg', groups=['search'], api_ver=2)
