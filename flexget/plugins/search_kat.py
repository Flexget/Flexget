import logging
import urllib
import feedparser
from flexget.entry import Entry
from flexget.utils.search import torrent_availability
from flexget.plugin import PluginWarning, register_plugin

log = logging.getLogger('kat')


class SearchKAT(object):
    """KAT search plugin.

    should accept:
    kat: <category>

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

        root = validator.factory('choice')
        root.accept_choices(['all', 'movies', 'tv', 'music', 'books', 'xxx', 'other'])
        return root

    def search(self, query, comparator, config):
        comparator.set_seq1(query)
        name = comparator.search_string().lower()
        url = 'http://www.kat.ph/search/%s/?rss=1' % urllib.quote(name.encode('utf-8'))
        if config != 'all':
            url += '&category=%s' % config

        log.debug('requesting: %s' % url)
        rss = feedparser.parse(url)
        entries = []

        status = rss.get('status', False)
        if status != 200:
            raise PluginWarning('Search result not 200 (OK), received %s' % status)

        ex = rss.get('bozo_exception', False)
        if ex:
            raise PluginWarning('Got bozo_exception (bad feed)')

        for item in rss.entries:
            # Check if item passes comparator
            comparator.set_seq2(item.title)
            log.debug('name: %s, found name: %s, confidence: %s' % (comparator.a, comparator.b, comparator.ratio()))
            if not comparator.matches():
                continue

            entry = Entry()
            entry['title'] = item.title
            if item.torrentlink.startswith('//'):
                entry['url'] = 'http:' + item.torrentlink
            else:
                entry['url'] = item.torrentlink
            entry['search_ratio'] = comparator.ratio()
            entry['torrent_seeds'] = int(item.seeds)
            entry['torrent_leeches'] = int(item.leechs)
            entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
            entry['content_size'] = int(item.size) / 1024 / 1024
            entry['torrent_info_hash'] = item.hash

            entries.append(entry)

        # choose torrent
        if not entries:
            raise PluginWarning('No matches for %s' % name, log, log_once=True)

        entries.sort(reverse=True, key=lambda x: x.get('search_sort'))
        return entries

register_plugin(SearchKAT, 'kat', groups=['search'])
