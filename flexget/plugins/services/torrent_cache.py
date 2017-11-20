from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re
import random

from flexget import plugin
from flexget.event import event

log = logging.getLogger('torrent_cache')

MIRRORS = [
    'https://thetorrent.org/',
    'http://torrage.com/torrent/',
    'http://zoink.it/torrent/',
    'http://itorrents.org/torrent/',
]


class TorrentCache(object):
    """Adds urls to torrent cache sites to the urls list."""

    def infohash_urls(self, info_hash):
        """
        Other plugins may use this to make downloadable URLs
        from infohash.

        :param str info_hash: Torrent infohash
        :returns: shuffled urls from which infohash can be retrieved
        """
        urls = [host + info_hash.upper() + '.torrent' for host in MIRRORS]
        random.shuffle(urls)
        return urls

    @plugin.priority(120)
    def on_task_urlrewrite(self, task, config):
        for entry in task.accepted:
            info_hash = None
            if entry['url'].startswith('magnet:'):
                info_hash_search = re.search('btih:([0-9a-f]+)', entry['url'], re.IGNORECASE)
                if info_hash_search:
                    info_hash = info_hash_search.group(1)
            elif entry.get('torrent_info_hash'):
                info_hash = entry['torrent_info_hash']
            if info_hash:
                entry.setdefault('urls', [entry['url']])
                urls = set(host + info_hash.upper() + '.torrent' for host in MIRRORS)
                # Don't add any duplicate addresses
                urls = list(urls - set(entry['urls']))
                # Add the cache mirrors in a random order
                random.shuffle(urls)
                entry['urls'].extend(urls)


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentCache, 'torrent_cache', api_ver=2, builtin=True)
