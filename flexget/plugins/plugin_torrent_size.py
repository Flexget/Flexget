import logging
from flexget.plugin import *
from sys import maxint

log = logging.getLogger('torrent_size')


class TorrentSize(object):
    """
    Provides file size information when dealing with torrents
    """

    @priority(200)
    def on_feed_modify(self, feed):
        for entry in feed.accepted + feed.entries:
            if 'torrent' in entry:
                size = entry['torrent'].get_size() / 1024 / 1024
                log.debug('%s size: %s MB' % (entry['title'], size))
                entry['content_size'] = size


register_plugin(TorrentSize, 'torrent_size', builtin=True)
