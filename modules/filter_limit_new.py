import logging

__pychecker__ = 'unusednames=parser'

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

    def register(self, manager, parser):
        manager.register('limit_new')

    def validator(self):
        import validator
        return validator.factory('number')

    def feed_filter(self, feed):
        # purge filtered items since we don't want to pass any of them
        # since they are most likelly useless
        feed._purge() 
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
