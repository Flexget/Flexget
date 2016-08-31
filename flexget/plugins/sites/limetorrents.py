from __future__ import unicode_literals, division, absolute_import
from future.moves.urllib.parse import quote
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability
from flexget.utils.tools import parse_filesize

log = logging.getLogger('limetorrents')


class Limetorrents(object):
    """
        Limetorrents search plugin.
    """

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'category': {'type': 'string', 'enum': ['all', 'anime', 'applications', 'games', 'movies', 'music',
                                                            'tv', 'other'], 'default': 'all'},
                    'order_by': {'type': 'string', 'enum': ['date', 'seeds'], 'default': 'date'}
                },
                'additionalProperties': False
            }
        ]
    }

    base_url = 'https://www.limetorrents.cc/'
    errors = False

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for entries on Limetorrents
        """

        if not isinstance(config, dict):
            config = {'category': config}

        order_by = ''
        if isinstance(config.get('order_by'), str):
            if config['order_by'] != 'date':
                order_by = '{0}/1'.format(config['order_by'])

        category = 'all'
        if isinstance(config.get('category'), str):
            category = '{0}'.format(config['category'])

        entries = set()

        for search_string in entry.get('search_strings', [entry['title']]):

            query = 'search/{0}/{1}/{2}'.format(category, quote(search_string.encode('utf8')), order_by)
            log.debug('Using search: %s; category: %s; ordering: %s', search_string, category, order_by or 'default')
            try:
                page = task.requests.get(self.base_url + query)
                log.debug('requesting: %s', page.url)
            except RequestException as e:
                log.error('Limetorrents request failed: %s', e)
                continue

            soup = get_soup(page.content)
            if soup.find('a', attrs={'class': 'csprite_dl14'}) is not None:
                for link in soup.findAll('a', attrs={'class': 'csprite_dl14'}):

                    row = link.find_parent('tr')
                    info_url = str(link.get('href'))

                    # Get the title from the URL as it's complete versus the actual Title text which gets cut off
                    title = str(link.next_sibling.get('href'))
                    title = title[:title.rfind('-torrent')].replace('-', ' ')
                    title = title[1:]

                    data = row.findAll('td', attrs={'class': 'tdnormal'})
                    size = str(data[1].text).replace(',', '')

                    seeds = int(row.find('td', attrs={'class': 'tdseed'}).text.replace(',', ''))
                    leeches = int(row.find('td', attrs={'class': 'tdleech'}).text.replace(',', ''))

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
    plugin.register(Limetorrents, 'limetorrents', groups=['search'], api_ver=2)
