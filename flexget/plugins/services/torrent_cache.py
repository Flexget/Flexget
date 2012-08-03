import logging
import re
import random
from flexget.plugin import register_plugin, priority

log = logging.getLogger('torrent_cache')

MIRRORS = ['http://torrage.com/torrent/',
           # Now using a landing page instead of going directly to the torrent
           # TODO: May be fixable by setting the referer
           #'http://torcache.net/torrent/',
           'http://zoink.it/torrent/',
           'http://torrage.ws/torrent/']


class TorrentCache(object):
    """Adds urls to torrent cache sites to the urls list."""

    @priority(-255)
    def on_task_filter(self, task, config):
        for entry in task.accepted:
            info_hash = None
            if entry['url'].startswith('magnet:'):
                info_hash_search = re.search('btih:([0-9a-f]+)', entry['url'], re.IGNORECASE)
                if info_hash_search:
                    info_hash = info_hash_search.group(1)
            elif entry.get('torrent_info_hash'):
                info_hash = entry['torrent_info_hash']
            if info_hash:
                # Add the mirrors in random order
                random.shuffle(MIRRORS)
                entry.setdefault('urls', [entry['url']])
                entry['urls'].extend(host + info_hash.upper() + '.torrent' for host in MIRRORS)


register_plugin(TorrentCache, 'torrent_cache', api_ver=2, builtin=True)
