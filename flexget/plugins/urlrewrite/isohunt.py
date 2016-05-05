from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import logging
import re

import feedparser

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.search import torrent_availability, normalize_unicode

log = logging.getLogger('isohunt')


class UrlRewriteIsoHunt(object):
    """IsoHunt urlrewriter and search plugin.

    should accept:
    isohunt: <category>

      categories:
      empty or -1: All
      0 : Misc.
      1 : Video/Movies
      2 : Audio
      3 : TV
      4 : Games
      5 : Apps
      6 : Pics
      7 : Anime
      8 : Comics
      9 : Books
      10: Music Video
      11: Unclassified
      12: ALL
    """

    schema = {
        'type': 'string',
        'enum': ['misc', 'movies', 'audio', 'tv', 'games', 'apps', 'pics', 'anime', 'comics', 'books', 'music video',
                 'unclassified', 'all']
    }

    def url_rewritable(self, task, entry):
        url = entry['url']
        # search is not supported
        if url.startswith('http://isohunt.com/torrents/?ihq='):
            return False
        # not replaceable
        if 'torrent_details' not in url:
            return False
        return url.startswith('http://isohunt.com') and url.find('download') == -1

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('torrent_details', 'download')

    def search(self, task, entry, config):
        # urllib.quote will crash if the unicode string has non ascii characters, so encode in utf-8 beforehand
        optionlist = ['misc', 'movies', 'audio', 'tv', 'games', 'apps', 'pics', 'anime', 'comics', 'books',
                      'music video', 'unclassified', 'all']
        entries = set()
        search_strings = [normalize_unicode(s) for s in entry.get('search_strings', [entry['title']])]
        for search_string in search_strings:
            url = 'http://isohunt.com/js/rss/%s?iht=%s&noSL' % (
                quote(search_string.encode('utf-8')), optionlist.index(config))

            log.debug('requesting: %s' % url)
            rss = feedparser.parse(url)

            status = rss.get('status', False)
            if status != 200:
                raise plugin.PluginWarning('Search result not 200 (OK), received %s' % status)

            ex = rss.get('bozo_exception', False)
            if ex:
                raise plugin.PluginWarning('Got bozo_exception (bad feed)')

            for item in rss.entries:
                entry = Entry()
                entry['title'] = item.title
                entry['url'] = item.link

                m = re.search(r'Size: ([\d]+).*Seeds: (\d+).*Leechers: (\d+)', item.description, re.IGNORECASE)
                if not m:
                    log.debug('regexp did not find seeds / peer data')
                    continue
                else:
                    log.debug('regexp found size(%s), Seeds(%s) and Leeches(%s)' % (m.group(1), m.group(2), m.group(3)))

                    entry['content_size'] = int(m.group(1))
                    entry['torrent_seeds'] = int(m.group(2))
                    entry['torrent_leeches'] = int(m.group(3))
                    entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])

                entries.add(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteIsoHunt, 'isohunt', groups=['urlrewriter', 'search'], api_ver=2)
