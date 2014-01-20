from __future__ import unicode_literals, division, absolute_import
import logging
import urllib

import feedparser

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.search import torrent_availability, normalize_unicode

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

    def search(self, entry, config):
        search_strings = [normalize_unicode(s).lower() for s in entry.get('search_strings', [entry['title']])]
        entries = set()
        for search_string in search_strings:
            search_string_url_fragment = search_string

            if config.get('verified'):
                search_string_url_fragment += ' verified:1'
            url = 'http://kickass.to/search/%s/?rss=1' % urllib.quote(search_string_url_fragment.encode('utf-8'))
            if config.get('category', 'all') != 'all':
                url += '&category=%s' % config['category']

            sorters = [{'field': 'time_add', 'sorder': 'desc'},
                       {'field': 'seeders', 'sorder': 'desc'}]
            for sort in sorters:
                url += '&field=%(field)s&sorder=%(sorder)s' % sort

                log.debug('requesting: %s' % url)
                rss = feedparser.parse(url)

                status = rss.get('status', False)
                if status == 404:
                    # Kat returns status code 404 when no results found for some reason...
                    log.debug('No results found for search query: %s' % search_string)
                    continue
                elif status != 200:
                    raise plugin.PluginWarning('Search result not 200 (OK), received %s' % status)

                ex = rss.get('bozo_exception', False)
                if ex:
                    raise plugin.PluginWarning('Got bozo_exception (bad feed)')

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
