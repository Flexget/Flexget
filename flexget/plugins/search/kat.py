from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import logging

import feedparser
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.search import torrent_availability, normalize_unicode, clean_title

log = logging.getLogger('kat')


class SearchKAT(object):
    """KAT search plugin.

    should accept:
    kat:
      category: <category>
      verified: yes/no

    categories:
      all
      movies
      tv
      music
      books
      xxx
      other
    """

    schema = {
        'type': 'object',
        'properties': {
            'category': {'type': 'string', 'enum': ['all', 'movies', 'tv', 'music', 'books', 'xxx', 'other']},
            'verified': {'type': 'boolean'}
        },
        'additionalProperties': False
    }

    def search(self, task, entry, config):
        search_strings = [normalize_unicode(s).lower() for s in entry.get('search_strings', [entry['title']])]
        entries = set()
        for search_string in search_strings:
            search_string = clean_title(search_string)
            search_string_url_fragment = search_string
            params = {'rss': 1}
            if config.get('verified'):
                search_string_url_fragment += ' verified:1'
            url = 'https://kat.cr/usearch/%s/' % quote(search_string_url_fragment.encode('utf-8'))
            if config.get('category', 'all') != 'all':
                params['category'] = config['category']

            sorters = [{'field': 'time_add', 'sorder': 'desc'},
                       {'field': 'seeders', 'sorder': 'desc'}]
            for sort in sorters:
                params.update(sort)

                log.debug('requesting: %s' % url)
                try:
                    r = task.requests.get(url, params=params, raise_status=False)
                except RequestException as e:
                    log.warning('Search resulted in: %s' % e)
                    continue
                if not r.content:
                    log.debug('No content returned from search.')
                    continue
                elif r.status_code != 200:
                    log.warning('Search returned %s response code' % r.status_code)
                    continue
                rss = feedparser.parse(r.content)

                ex = rss.get('bozo_exception', False)
                if ex:
                    log.warning('Got bozo_exception (bad feed)')
                    continue

                for item in rss.entries:
                    entry = Entry()
                    entry['title'] = item.title

                    if not item.get('enclosures'):
                        log.warning('Could not get url for entry from KAT. Maybe plugin needs updated?')
                        continue
                    entry['url'] = item.enclosures[0]['url']
                    entry['torrent_seeds'] = int(item.torrent_seeds)
                    entry['torrent_leeches'] = int(item.torrent_peers)
                    entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                    entry['content_size'] = int(item.torrent_contentlength) / 1024 / 1024
                    entry['torrent_info_hash'] = item.torrent_infohash

                    entries.add(entry)

                if len(rss.entries) < 25:
                    break

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchKAT, 'kat', groups=['search'], api_ver=2)
