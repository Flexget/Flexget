import urllib
import logging
import re
import types
from filter_patterns import FilterPatterns

log = logging.getLogger('ignore')

class IgnoreFilter(FilterPatterns):
    """
        Functionally this is identical to filter unconditionally, but instead
        of passing entries unconditionally entries are removed unconditionally.
        This is usefull for filtering entries containing certain patterns
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
        manager.register(instance=self, type='filter', keyword='ignore', callback=self.ignore, order=65535)

    def ignore(self, feed):
        self.filter(feed, feed.filter, None, 'ignore')

if __name__ == "__main__":
    print "works!"
