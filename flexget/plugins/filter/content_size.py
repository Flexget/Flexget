import logging
from sys import maxint
from flexget.plugin import register_plugin, priority
from flexget.utils.log import log_once

log = logging.getLogger('content_size')


class FilterContentSize(object):

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('number', key='min')
        config.accept('number', key='max')
        config.accept('boolean', key='strict')
        return config

    def process_entry(self, feed, entry):
        """Rejects this entry if it does not pass content_size requirements. Returns true if the entry was rejected."""
        config = feed.config.get('content_size', {})
        if 'content_size' in entry:
            size = entry['content_size']
            log.debug('%s size %s MB' % (entry['title'], size))
            # Avoid confusion by printing a reject message to info log, as
            # download plugin has already printed a downloading message.
            if size < config.get('min', 0):
                log_once('Entry `%s` too small, rejecting' % entry['title'], log)
                feed.reject(entry, 'minimum size %s MB, got %s MB' % (config['min'], size), remember=True)
                return True
            if size > config.get('max', maxint):
                log_once('Entry `%s` too big, rejecting' % entry['title'], log)
                feed.reject(entry, 'maximum size %s MB, got %s MB' % (config['max'], size), remember=True)
                return True

    @priority(150)
    def on_feed_modify(self, feed, config):
        if feed.manager.options.test or feed.manager.options.learn:
            log.info('Plugin is partially disabled with --test and --learn because size information may not be available')
            return

        num_rejected = len(feed.rejected)
        for entry in feed.accepted:
            if 'content_size' in entry:
                self.process_entry(feed, entry)
            elif config.get('strict', True):
                log.debug('Entry %s size is unknown, rejecting because of strict mode (default)' % entry['title'])
                log.info('No size information available for %s, rejecting' % entry['title'])
                if not 'file' in entry:
                    feed.reject(entry, 'no size available, file unavailable', remember=True)
                else:
                    feed.reject(entry, 'no size available from downloaded file', remember=True)

        if len(feed.rejected) > num_rejected:
            # Since we are rejecting after the filter event,
            # re-run this feed to see if there is an alternate entry to accept
            feed.rerun()


register_plugin(FilterContentSize, 'content_size', api_ver=2)
