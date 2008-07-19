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
        manager.register(event='filter', keyword='limit_new', callback=self.limit, order=65535)

    def validate(self, config):
        if not isinstance(config, int):
            return ['wrong datatype, expecting number']
        return []

    def limit(self, feed):
        # purge filtered items since we don't want to pass any of them
        # since they are most likelly useless
        feed._purge() 
        amount = feed.config.get('limit_new', len(feed.entries))
        i = 1
        for entry in feed.entries:
            if i > amount:
                log.debug('Rejecting %s' % entry)
                feed.reject(entry)
            i += 1
