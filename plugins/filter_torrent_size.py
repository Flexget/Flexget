import logging
from sys import maxint

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
        manager.register('torrent_size')

    def validator(self):
        import validator
        config = validator.factory('dict')
        config.accept('number', key='min')
        config.accept('number', key='max')
        return config

    def feed_modify(self, feed):
        config = feed.config['torrent_size']
        for entry in feed.accepted:
            if 'torrent' in entry:
                size = entry['torrent'].size / 1024 / 1024
                log.debug('Size: %s MB' % size)
                if size < config.get('min', 0):
                    log.debug('Torrent too small, rejecting')
                    feed.reject(entry, 'minimum size')
                if size > config.get('max', maxint):
                    log.debug('Torrent too big, rejecting')
                    feed.reject(entry, 'maximum size')
            else:
                # not a torrent?
                log.debug('Entry %s is not a torrent' % entry['title'])