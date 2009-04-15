import logging

log = logging.getLogger('accept_all')

class FilterAcceptAll:

    """
        Just accepts all entries.
        
        Example:
        
        accept_all: true
    """

    def register(self, manager, parser):
        manager.register('accept_all')
        
    def validator(self):
        import validator
        return validator.factory('boolean')

    def feed_filter(self, feed):
        for entry in feed.entries:
            feed.accept(entry)