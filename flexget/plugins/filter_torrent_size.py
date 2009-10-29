import logging
from flexget.plugin import *
from sys import maxint

log = logging.getLogger('torrent_size')

class FilterTorrentSize:
    """
        Example:

        torrent_size:
          min: 12
          max: 1200
          strict: yes

        Unit is MB
        Optional strict flag will cause all non-torrents to be rejected.
        
    """
    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('number', key='min')
        config.accept('number', key='max')
        config.accept('boolean', key='strict')
        return config

    def on_feed_modify(self, feed):
        if feed.manager.options.test:
            log.info('plugin is disabled in test mode as size information is not available')
            return
        config = feed.config['torrent_size']
        for entry in feed.accepted + feed.entries:
            if 'torrent' in entry:
                size = entry['torrent'].get_size() / 1024 / 1024
                log.debug('%s size: %s MB' % (entry['title'], size))
                rejected = False
                if size < config.get('min', 0):
                    log.debug('Torrent too small, rejecting')
                    feed.reject(entry, 'minimum size')
                    rejected = True
                if size > config.get('max', maxint):
                    log.debug('Torrent too big, rejecting')
                    feed.reject(entry, 'maximum size')
                    rejected = True
                # learn this as seen that it won't be re-downloaded & rejected on every execution
                if rejected:
                    get_plugin_by_name('seen').instance.learn(feed, entry)
            else:
                if config.get('strict', False):
                    feed.reject(entry, 'not a torrent')
                log.debug('Entry %s is not a torrent' % entry['title'])

register_plugin(FilterTorrentSize, 'torrent_size')
