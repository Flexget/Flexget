import logging
from flexget.feed import Entry
import re
import urllib
from flexget.plugin import *
import difflib
import feedparser

log = logging.getLogger('torrentz')

REGEXP = re.compile(r'http://torrentz\.eu/(?P<hash>[a-f0-9]{40})')


class UrlRewriteTorrentz(object):
    """Torrentz urlrewriter."""

    def url_rewritable(self, feed, entry):
        return REGEXP.match(entry['url'])

    def url_rewrite(self, feed, entry):
        hash = REGEXP.match(entry['url']).group(1)
        entry['url'] = 'http://zoink.it/torrent/%s.torrent' % hash.upper()

    def search(self, query, config=None):
        entries = self.search_title(query)
        log.debug('Search got %d results' % len(entries))
        return entries

    def search_title(self, name):
        url = 'http://torrentz.eu/feed?q=%s' % urllib.quote(name)
        log.debug('requesting: %s' % url)
        rss = feedparser.parse(url)
        clean_name = name.replace('.', ' ').replace('-', '').replace('_', ' ').lower()
        entries = []

        status = rss.get('status', False)
        if status != 200:
            raise PluginWarning('Search result not 200 (OK), received %s' % status)

        ex = rss.get('bozo_exception', False)
        if ex:
            raise PluginWarning('Got bozo_exception (bad feed)')

        for item in rss.entries:
            # assign confidence score of how close this link is to the name you're looking for. .6 and above is "close"
            confidence = difflib.SequenceMatcher(lambda x: x in ' -._', # junk characters
                                       item.title.lower().replace('.', ' ').replace('-', '').replace('_', ' '),
                                       clean_name).ratio()
            log.debug('name: %s' % clean_name)
            log.debug('found name: %s' % item.title.lower().replace('.', ' ').replace('-', '').replace('_', ' '))
            log.debug('confidence: %s' % str(confidence))
            if confidence < 0.9:
                continue

            m = re.search(r'Seeds: ([,\d]+) Peers: ([,\d]+)', item.description, re.IGNORECASE)
            if not m:
                log.debug('regexp did not find seeds / peer data')
                continue

            entry = Entry()
            entry['title'] = item.title
            entry['url'] = item.link
            entry['torrent_seeds'] = int(m.group(1).replace(',', ''))
            entry['torrent_leeches'] = int(m.group(2).replace(',', ''))
            entries.append(entry)

        # choose torrent
        if not entries:
            raise PluginWarning('No close matches for %s' % name, log, log_once=True)

        def score(a):
            return a['torrent_seeds'] * 2 + a['torrent_leeches']

        entries.sort(reverse=True, key=score)

        return entries

register_plugin(UrlRewriteTorrentz, 'torrentz', groups=['urlrewriter', 'search'])
