from __future__ import unicode_literals, division, absolute_import
import logging
import urllib
import feedparser
from flexget.entry import Entry
from flexget.utils.search import torrent_availability, normalize_unicode
from flexget.plugin import PluginWarning, register_plugin

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

    def validator(self):
        from flexget import validator

        root = validator.factory('dict')
        root.accept('choice', key='category').accept_choices(['all', 'movies', 'tv', 'music', 'books', 'xxx', 'other'])
        root.accept('boolean', key='verified')
        return root

    def search(self, entry, config):
        search_strings = [normalize_unicode(s).lower() for s in entry.get('search_strings', [entry['title']])]
        entries = set()
        for search_string in search_strings:
            if config.get('verified'):
                search_string += ' verified:1'
            url = 'http://kickass.to/search/%s/?rss=1' % urllib.quote(search_string.encode('utf-8'))
            if config.get('category', 'all') != 'all':
                url += '&category=%s' % config['category']

            log.debug('requesting: %s' % url)
            rss = feedparser.parse(url)

            status = rss.get('status', False)
            if status != 200:
                raise PluginWarning('Search result not 200 (OK), received %s' % status)

            ex = rss.get('bozo_exception', False)
            if ex:
                raise PluginWarning('Got bozo_exception (bad feed)')

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

        return entries

register_plugin(SearchKAT, 'kat', groups=['search'])
