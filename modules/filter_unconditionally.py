import urllib
import logging
import re
import types

from filter_patterns import FilterPatterns

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('unconditionally')

class UnconditionallyFilter(FilterPatterns):

    """
        Entries matching regexp will be accepted.
        Non matching entries are not intervened.
        
        Example:

        imdb:
          min_score: 6.4
        unconditionally:
          - rush.hour.3

        Now rush hour 3 will be passed even if imdb filter would cause it
        to be filtered because of min_score.

        See module patterns documentation for full syntax.
    """

    def register(self, manager, parser):
        manager.register(instance=self, event="filter", keyword="unconditionally", callback=self.unconditionally, order=65536)

    def unconditionally(self, feed):
        self.filter(feed, feed.accept, None, 'unconditionally')     

if __name__ == "__main__":
    pass
