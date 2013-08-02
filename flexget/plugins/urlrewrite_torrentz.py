from __future__ import unicode_literals, division, absolute_import
import logging
import re
import urllib
import urllib2
import feedparser

from flexget.plugin import register_plugin, PluginWarning
from flexget.entry import Entry
from flexget.utils.search import torrent_availability, normalize_unicode
from flexget import validator

log = logging.getLogger('torrentz')

REGEXP = re.compile(r'http://torrentz\.eu/(?P<hash>[a-f0-9]{40})')
REPUTATIONS = {  # Maps reputation name to feed address
    'any': 'feed_any',
    'low': 'feed_low',
    'good': 'feed',
    'verified': 'feed_verified'
}


class UrlRewriteTorrentz(object):
    """Torrentz urlrewriter."""

    def validator(self):
        root = validator.factory('choice')
        root.accept_choices(REPUTATIONS)
        return root

    def url_rewritable(self, task, entry):
        return REGEXP.match(entry['url'])

    def url_rewrite(self, task, entry):
        thash = REGEXP.match(entry['url']).group(1)
        entry['url'] = 'https://torcache.net/torrent/%s.torrent' % thash.upper()
        entry['torrent_info_hash'] = thash

    def search(self, entry, config=None):
        if config:
            feed = REPUTATIONS[config]
        else:
            feed = REPUTATIONS['good']
        entries = set()
        for search_string in entry.get('search_string', [entry['title']]):
            query = normalize_unicode(search_string)
            # urllib.quote will crash if the unicode string has non ascii characters, so encode in utf-8 beforehand
            url = 'http://torrentz.eu/%s?q=%s' % (feed, urllib.quote(query.encode('utf-8')))
            log.debug('requesting: %s' % url)
            try:
                opened = urllib2.urlopen(url)
            except urllib2.URLError, err:
                raise PluginWarning('Error requesting URL: %s' % err)
            rss = feedparser.parse(opened)

            status = rss.get('status', False)
            if status != 200:
                raise PluginWarning(
                    'Search result not 200 (OK), received %s %s' %
                    (status, opened.msg))

            ex = rss.get('bozo_exception', False)
            if ex:
                raise PluginWarning('Got bozo_exception (bad feed)')

            for item in rss.entries:
                m = re.search(r'Size: ([\d]+) Mb Seeds: ([,\d]+) Peers: ([,\d]+) Hash: ([a-f0-9]+)',
                              item.description, re.IGNORECASE)
                if not m:
                    log.debug('regexp did not find seeds / peer data')
                    continue

                entry = Entry()
                entry['title'] = item.title
                entry['url'] = item.link
                entry['content_size'] = int(m.group(1))
                entry['torrent_seeds'] = int(m.group(2).replace(',', ''))
                entry['torrent_leeches'] = int(m.group(3).replace(',', ''))
                entry['torrent_info_hash'] = m.group(4).upper()
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                entries.add(entry)

        log.debug('Search got %d results' % len(entries))
        return entries

register_plugin(UrlRewriteTorrentz, 'torrentz', groups=['urlrewriter', 'search'])
