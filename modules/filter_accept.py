import urllib
import logging
import re

from filter_patterns import FilterPatterns

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('accept')

class AcceptFilter(FilterPatterns):

    """
        Entries matching regexp will be accepted.
        Non matching entries are not intervened.
        
        Example:

        imdb:
          min_score: 6.4
        accept:
          - rush.hour.3

        Now rush hour 3 will be passed even if imdb filter would cause it
        to be filtered because of min_score.

        See module patterns documentation for full syntax.
    """

    def register(self, manager, parser):
        manager.register('accept') 
        
    def feed_filter(self, feed):
        self.filter(feed, feed.accept, None, 'accept')
