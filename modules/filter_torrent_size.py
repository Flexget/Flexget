import yaml
import sys
import logging

log = logging.getLogger('torrent_size')

class FilterTorrentSize:

    """
        Example:

        torrent_size:
          min: 12
          max: 1200

        Untested, may not work!
    """

    def register(self, manager, parser):
        manager.register(instance=self, event='modify', keyword='torrent_size', callback=self.run)

    def run(self, feed):
        config = feed.config['torrent_size']
        for entry in feed.entries:
            if entry.has_key('torrent'):
                size = entry['torrent'].size / 1024 / 1024
                if size < config.get('min', 0):
                    log.debug('Torrent too small, rejecting')
                    feed.reject(entry)
                if size > config.get('max', sys.maxint):
                    log.debug('Torrent too big, rejecting')
                    feed.reject(entry)
            else:
                # not a torrent?
                log.debug('Entry %s is not a torrent?' % entry['title'])
