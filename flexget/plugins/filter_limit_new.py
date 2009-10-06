import logging
from flexget.plugin import *

log = logging.getLogger('limit_new')

class FilterLimitNew:
    """
        Limit number of new items.

        Example:

        limit_new: 1

        This would allow only one new item to pass trough per execution.
        Useful for passing torrents slowly into download.
        
        Note that since this is per execution, actual rate depends how often
        FlexGet is executed.
    """
    def validator(self):
        from flexget import validator
        return validator.factory('number')

    def on_feed_filter(self, feed):
        amount = feed.config.get('limit_new', len(feed.entries))
        i = 1
        rejected = 0
        passed = 0
        for entry in feed.entries:
            if i > amount:
                rejected += 1
                feed.reject(entry)
            else:
                passed += 1
            i += 1
        log.debug('Rejected: %s Passed: %s' % (rejected, passed))

register_plugin(FilterLimitNew, 'limit_new')
