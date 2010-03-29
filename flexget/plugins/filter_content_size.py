import logging
import os
from sys import maxint
from flexget.plugin import *

log = logging.getLogger('content_size')


class FilterContentSize(object):

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('number', key='min')
        config.accept('number', key='max')
        config.accept('boolean', key='strict')
        return config

    def on_feed_modify(self, feed):
        if feed.manager.options.test:
            log.info('Plugin is disabled in test mode as size information is not available')
            return

        config = feed.config.get('content_size', {})
        for entry in feed.accepted:
            rejected = False
            if 'content_size' in entry:
                size = entry['content_size']
                log.debug('%s size %s MB' % (entry['title'], size))
                if size < config.get('min', 0):
                    log.debug('Entry %s too small, rejecting' % entry['title'])
                    feed.reject(entry, 'minimum size (%s MB)' % config['min'])
                    rejected = True
                if size > config.get('max', maxint):
                    log.debug('Entry %s too big, rejecting' % entry['title'])
                    feed.reject(entry, 'maximum size (%s MB)' % config['max'])
                    rejected = True
            else:
                if config.get('strict', True):
                    log.debug('Entry %s size is unknown, rejecting because of strict mode (default)' % entry['title'])
                    feed.reject(entry, 'no size available')
                    rejected = True

            # learn this as seen that it won't be re-downloaded & rejected on every execution
            if rejected:
                get_plugin_by_name('seen').instance.learn(feed, entry)
                # clean up temporary files
                if not feed.manager.unit_test:
                    if os.path.exists(entry.get('file', '')):
                        os.remove(entry['file'])
                        del(entry['file'])

register_plugin(FilterContentSize, 'content_size', priorities={'modify': 150})
