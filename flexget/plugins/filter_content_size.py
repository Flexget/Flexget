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

    @priority(150)
    def on_feed_modify(self, feed):
        if feed.manager.options.test or feed.manager.options.learn:
            log.info('Plugin is disabled with --test and --learn because size information is not available')
            return
            
        config = feed.config.get('content_size', {})
        for entry in feed.accepted:
            if 'content_size' in entry:
                size = entry['content_size']
                log.debug('%s size %s MB' % (entry['title'], size))
                # Avoid confusion by printing a reject message to info log, as
                # download plugin has alredy printed a downloading message.
                if size < config.get('min', 0):
                    log.info('Entry %s too small, rejecting' % entry['title'])
                    feed.reject(entry, 'minimum size (%s MB)' % config['min'])
                if size > config.get('max', maxint):
                    log.info('Entry %s too big, rejecting' % entry['title'])
                    feed.reject(entry, 'maximum size (%s MB)' % config['max'])
            else:
                if config.get('strict', True):
                    log.debug('Entry %s size is unknown, rejecting because of strict mode (default)' % entry['title'])
                    log.info('No size information available for %s, rejecting' % entry['title'])
                    feed.reject(entry, 'no size available')

            # learn this as seen that it won't be re-downloaded & rejected on every execution
            if entry in feed.rejected:
                get_plugin_by_name('seen').instance.learn(feed, entry)
                # clean up temporary files
                if not feed.manager.unit_test:
                    if os.path.exists(entry.get('file', '')):
                        log.debug('removing temp %s' % entry['file'])
                        os.remove(entry['file'])
                        del(entry['file'])

register_plugin(FilterContentSize, 'content_size')
