from __future__ import unicode_literals, division, absolute_import
import logging
import re
import urllib
import feedparser

from flexget.plugin import register_plugin, PluginWarning
from flexget.entry import Entry
from flexget.utils.search import torrent_availability, StringComparator
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

    def search(self, query, comparator=StringComparator(), config=None):
        if config:
            feed = REPUTATIONS[config]
        else:
            feed = REPUTATIONS['good']
        # urllib.quote will crash if the unicode string has non ascii characters, so encode in utf-8 beforehand
        comparator.set_seq1(query)
        query = comparator.search_string()
        url = 'http://torrentz.eu/%s?q=%s' % (feed, urllib.quote(query.encode('utf-8')))
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
            entry['search_ratio'] = comparator.ratio()
            entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
            entries.append(entry)

        # choose torrent
        if not entries:
            raise PluginWarning('No close matches for %s' % query, log, log_once=True)

        entries.sort(reverse=True, key=lambda x: x.get('search_sort'))
        log.debug('Search got %d results' % len(entries))
        return entries

register_plugin(UrlRewriteTorrentz, 'torrentz', groups=['urlrewriter', 'search'])
