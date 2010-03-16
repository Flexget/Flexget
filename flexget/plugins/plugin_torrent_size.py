import logging
from flexget.plugin import *
from sys import maxint

log = logging.getLogger('torrent_size')


class TorrentSize:
    """
    Provides file size information when dealing with torrents
    """

    def on_feed_modify(self, feed):
        for entry in feed.accepted + feed.entries:
            if 'torrent' in entry:
                size = entry['torrent'].get_size() / 1024 / 1024
                log.debug('%s size: %s MB' % (entry['title'], size))
                entry['content_size'] = size


register_plugin(TorrentSize, 'torrent_size', builtin=True, priorities={'modify': 200})
