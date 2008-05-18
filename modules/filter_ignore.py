import urllib
import logging
import re
import types
from filter_patterns import FilterPatterns

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('ignore')

class IgnoreFilter(FilterPatterns):
    """
        Entries matching regexp will be rejected.
        Non matching entries are not intervened.
        
        This is usefull for rejecting entries containing certain patterns
        globally by using global section.
        
        Example:

        global:
          ignore:
            - pattern 1

        feeds:
          feed A:
            patterns:
              - pattern 2
          feed B:
            patterns:
              - pattern 3

        Entries containing pattern 1 are not downloaded even if they also
        match to patterns 2, 3 or pass any other feed filters.

        Supports same syntax as patterns.
    """

    def register(self, manager, parser):
        manager.register(instance=self, event='filter', keyword='ignore', callback=self.ignore, order=65535)

    def ignore(self, feed):
        self.filter(feed, feed.reject, None, 'ignore')
