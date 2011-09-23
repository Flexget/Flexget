import logging
import re
import urllib
import feedparser
from flexget.plugin import register_plugin, PluginWarning
from flexget.feed import Entry
from flexget.utils.search import torrent_availability, StringComparator

log = logging.getLogger('torrentz')

REGEXP = re.compile(r'http://torrentz\.eu/(?P<hash>[a-f0-9]{40})')


class UrlRewriteTorrentz(object):
    """Torrentz urlrewriter."""

    def url_rewritable(self, feed, entry):
        return REGEXP.match(entry['url'])

    def url_rewrite(self, feed, entry):
        hash = REGEXP.match(entry['url']).group(1)
        entry['url'] = 'http://zoink.it/torrent/%s.torrent' % hash.upper()

    def search(self, query, comparator, config=None):
        entries = self.search_title(query, comparator)
        log.debug('Search got %d results' % len(entries))
        return entries

    def search_title(self, name, comparator=StringComparator()):
        # urllib.quote will crash if the unicode string has non ascii characters, so encode in utf-8 beforehand
        comparator.set_seq1(name)
        name = comparator.search_string()
        url = 'http://torrentz.eu/feed?q=%s' % urllib.quote(name.encode('utf-8'))
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
            # assign confidence score of how close this link is to the name you're looking for. .6 and above is "close"
            comparator.set_seq2(item.title)
            log.debug('name: %s' % comparator.a)
            log.debug('found name: %s' % comparator.b)
            log.debug('confidence: %s' % comparator.ratio())
            if not comparator.matches():
                continue

            m = re.search(r'Size: ([\d]+) Mb Seeds: ([,\d]+) Peers: ([,\d]+)', item.description, re.IGNORECASE)
            if not m:
                log.debug('regexp did not find seeds / peer data')
                continue

            entry = Entry()
            entry['title'] = item.title
            entry['url'] = item.link
            entry['content_size'] = int(m.group(1))
            entry['torrent_seeds'] = int(m.group(2).replace(',', ''))
            entry['torrent_leeches'] = int(m.group(3).replace(',', ''))
            entry['search_ratio'] = comparator.ratio()
            entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
            entries.append(entry)

        # choose torrent
        if not entries:
            raise PluginWarning('No close matches for %s' % name, log, log_once=True)

        entries.sort(reverse=True, key=lambda x: x.get('search_sort'))

        return entries

register_plugin(UrlRewriteTorrentz, 'torrentz', groups=['urlrewriter', 'search'])
