from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import logging
import re
import feedparser

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.search import normalize_unicode

log = logging.getLogger('extratorrent')

REGEXP = re.compile(r'https?://extratorrent.cc/torrent/([0-9]+)/(.*).html')

CATEGORIES = {
    'all': None,
    'music': 5,
    'anime': 1,
    'adult': 533,
    'movies': 4,
    'tv': 8,
}


class UrlRewriteExtraTorrent(object):
    """
    ExtraTorrent search plugin.

    should accept:
    kat:
        category: <category>

    categories:
        all
        music
        anime
        adult
        movies
        tv
    """

    schema = {
        'type': 'object',
        'properties': {
            'category': {'type': 'string', 'enum': ['all', 'music', 'anime', 'adult', 'movies', 'tv']},
        },
        'additionalProperties': False
    }

    def url_rewritable(self, task, entry):
        return REGEXP.match(entry['url']) is not None

    def url_rewrite(self, task, entry):
        match = REGEXP.match(entry['url'])
        torrent_id = match.group(1)
        torrent_name = match.group(2)
        entry['url'] = 'http://extratorrent.cc/download/%s/%s.torrent' % (torrent_id, torrent_name)

    def search(self, task, entry, config=None):
        if not isinstance(config, dict):
            config = {}

        category = CATEGORIES.get(config.get('category', 'all'), None)
        category_query = '&cid=%d' % category if category else ''

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)

            search_query = '&search=%s' % quote(query.encode('utf-8'))

            url = ('http://extratorrent.cc/rss.xml?type=search%s%s' %
                   (category_query, search_query))

            log.debug('Using %s as extratorrent search url' % url)

            rss = feedparser.parse(url)
            status = rss.get('status', False)
            if status != 200:
                log.debug('Search result not 200 (OK), received %s' % status)
            if not status or status >= 400:
                continue

            for item in rss.entries:
                entry = Entry()
                entry['title'] = item.title
                entry['url'] = item.link
                entry['content_size'] = int(item.size) / 1024 / 1024
                entry['torrent_info_hash'] = item.info_hash

                if isinstance(item.seeders, int):
                    entry['torrent_seeds'] = int(item.seeders)

                if isinstance(item.leechers, int):
                    entry['torrent_leeches'] = int(item.leechers)

                entries.add(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteExtraTorrent, 'extratorrent', groups=['urlrewriter', 'search'], api_ver=2)
