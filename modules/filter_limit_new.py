import logging

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
        manager.register(instance=self, event='filter', keyword='limit_new', callback=self.limit, order=65535)

    def limit(self, feed):
        feed._purge() # purge filtered items since we don't want to leave them
        amount = feed.config.get('limit_new', len(feed.entries))
        i = 1
        for entry in feed.entries:
            if i > amount:
                log.debug('Rejecting %s' % entry)
                feed.reject(entry)
            i += 1
