from __future__ import unicode_literals, division, absolute_import
from future.moves.urllib.parse import quote
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability
from flexget.utils.tools import parse_filesize
from flexget.plugins.internal.urlrewriting import UrlRewritingError

log = logging.getLogger('1337x')


class Site1337x(object):
    """
        1337x search plugin.
    """

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'order_by': {'type': 'string', 'enum': ['seeders', 'leechers', 'time', 'size'],
                                 'default': 'seeders'}
                },
                'additionalProperties': False
            }
        ]
    }

    base_url = 'http://1337x.to/'
    errors = False

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
            page = task.requests.get(url)
            log.debug('requesting: %s', page.url)
        except RequestException as e:
            log.error('1337x request failed: %s', e)
            raise UrlRewritingError('1337x request failed: %s', e)

        soup = get_soup(page.content)

        magnet_url = str(soup.find('a', id='magnetdl').get('href')).lower()
        torrent_url = str(soup.find('a', id='torrentdl').get('href')).lower()

        entry['url'] = torrent_url
        entry.setdefault('urls', []).append(torrent_url)
        entry['urls'].append(magnet_url)

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for entries on 1337x
        """

        if not isinstance(config, dict):
            config = {}

        order_by = ''
        sort_order = ''
        if isinstance(config.get('order_by'), str):
            if config['order_by'] != 'leechers':
                order_by = '/{0}/desc'.format(config['order_by'])
                sort_order = 'sort-'

        entries = set()

        for search_string in entry.get('search_strings', [entry['title']]):

            query = '{0}search/{1}{2}/1/'.format(sort_order, quote(search_string.encode('utf8')), order_by)
            log.debug('Using search params: %s; ordering by: %s', search_string, order_by or 'default')
            try:
                page = task.requests.get(self.base_url + query)
                log.debug('requesting: %s', page.url)
            except RequestException as e:
                log.error('1337x request failed: %s', e)
                continue

            soup = get_soup(page.content)
            if soup.find('div', attrs={'class': 'tab-detail'}) is not None:
                for link in soup.find('div', attrs={'class': 'tab-detail'}).findAll('a', href=re.compile('^/torrent/')):

                    li = link.parent.parent.parent

                    title = str(link.text).replace('...', '')
                    info_url = self.base_url + str(link.get('href'))[1:]
                    seeds = int(li.find('span', class_='green').string)
                    leeches = int(li.find('span', class_='red').string)
                    size = str(li.find('div', class_='coll-4').string)

                    size = parse_filesize(size)

                    e = Entry()

                    e['url'] = info_url
                    e['title'] = title
                    e['torrent_seeds'] = seeds
                    e['torrent_leeches'] = leeches
                    e['search_sort'] = torrent_availability(e['torrent_seeds'], e['torrent_leeches'])
                    e['content_size'] = size

                    entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Site1337x, '1337x', groups=['urlrewriter', 'search'], api_ver=2)
