import logging

log = logging.getLogger('accept_all')

class FilterAcceptAll:

    """
        Just accepts all entries.
        
        Example:
        
        accept_all: true
    """

    __plugin__ = 'accept_all'

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def feed_filter(self, feed):
        for entry in feed.entries:
            feed.accept(entry)
