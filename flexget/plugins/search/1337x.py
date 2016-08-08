from __future__ import unicode_literals, division, absolute_import
from future.moves.urllib.parse import quote
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin, db_schema
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import TimedLimiter, RequestException
from flexget.utils.requests import Session as RequestSession
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability

log = logging.getLogger('1337x')
Base = db_schema.versioned_base('1337x', 0)

requests = RequestSession()
requests.add_domain_limiter(TimedLimiter('1337x.to', '5 seconds'))  # TODO find out if they want a delay

class _1337x(object):
    """
        1337x search plugin.
    """

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'order_by': {'type': 'string', 'enum': ['seeders', 'leechers', 'time', 'size'], 'default': 'seeders'}
                },
                'additionalProperties': False
            }
        ]
    }

    base_url = 'http://1337x.to/'
    errors = False

    def get(self, url, params):
        """
        Wrapper to allow refreshing the cookie if it is invalid for some reason
        :param url:
        :param params:
        :return:
        """
        cookies = None

        response = requests.get(url, params=params, cookies=cookies)

        return response

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.endswith('.torrent'):
            return False
        if url.startswith('http://1337x.to/'):
            return True
        return False

    def url_rewrite(self, task, entry):
        """
            Gets the download information for 1337x result
        """

        url = entry['url']

        log.info('1337x rewriting download url: %s' % url)

        try:
            page = self.get(url, None)
            log.debug('requesting: %s', page.url)
        except RequestException as e:
            log.error('1337x request failed: %s', e)

        soup = get_soup(page.content)

        # Get the infohash - not needed but the code is here *shrugs*
        #infohash = str(soup.find("div", class_="infohash-box").contents)
        #infohash = infohash[-(len(infohash)-infohash.find(':'))+2:]
        #infohash = infohash[:infohash.find(' ')]

        magnetURL = str(soup.find("a", id="magnetdl").get('href')).lower()
        torrentURL = str(soup.find("a", id="torrentdl").get('href')).lower()

        # Can't update the title to the full title name because it breaks entry.remove
        #title = str(soup.title.string).replace("Download Torrent ","").replace("| 1337x","")

        entry['url'] = torrentURL
        entry['urls'] = []
        entry['urls'].append(torrentURL)
        entry['urls'].append(magnetURL)

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for entries on 1337x
        """

        if not isinstance(config, dict):
            config = {}

        order_by = ""
        sorted = ""
        if (isinstance(config.get('order_by'), str)):
            if (config['order_by'] != "leechers"):
                order_by = "/{0}/desc" . format(config['order_by'])
                sorted = "sort-"

        entries = set()

        for search_string in entry.get('search_strings', [entry['title']]):

            query = "{0}search/{1}{2}/1/" . format(sorted,quote(search_string.encode('utf8')), order_by)
            log.debug('Using search params: {0}; ordering by: {1}' . format(search_string, order_by or "default"))
            try:
                page = self.get(self.base_url + query, None)
                log.debug('requesting: %s', page.url)
            except RequestException as e:
                log.error('1337x request failed: %s', e)
                continue

            soup = get_soup(page.content)
            if (soup.find('div', attrs={'class': 'tab-detail'}) != None):
                for link in soup.find('div', attrs={'class': 'tab-detail'}).findAll('a',href=re.compile('^/torrent/')):

                    li = link.parent.parent.parent

                    title = str(link.text).replace("...","")
                    infoUrl = self.base_url + str(link.get('href'))[1:]
                    seeds = int(li.find("span", class_="green").string)
                    leeches = int(li.find("span", class_="red").string)
                    size = str(li.find("div", class_="coll-4").string)

                    if size.split( )[1] == 'GB':
                        size = int(float(size.split( )[0].replace(',', '')) * 1000 ** 3 / 1024 ** 2)
                    elif size.split( )[1] == 'MB':
                        size = int(float(size.split( )[0].replace(',', '')) * 1000 ** 2 / 1024 ** 2)
                    elif size.split( )[1] == 'KB':
                        size = int(float(size.split( )[0].replace(',', '')) * 1000 / 1024 ** 2)
                    else:
                        size = int(float(size.split( )[0].replace(',', '')) / 1024 ** 2)

                    #print("Title: {0}; Seeds: {1}; Leech: {2}, Size: {3}" . format(title,seeds,leeches,size))

                    e = Entry()

                    e['url'] = infoUrl
                    e['title'] = title
                    e['torrent_seeds'] = seeds
                    e['torrent_leeches'] = leeches
                    e['search_sort'] = torrent_availability(e['torrent_seeds'], e['torrent_leeches'])
                    e['content_size'] = size

                    entries.add(e)

        return entries

@event('plugin.register')
def register_plugin():
    plugin.register(_1337x, '1337x', groups=['urlrewriter', 'search'], api_ver=2)
