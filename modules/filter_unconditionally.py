

import urllib
import logging
import re
import types

from filter_patterns import FilterPatterns

class UnconditionallyFilter(FilterPatterns):
    """
        Functionally this is identical to filter patterns, but
        instead of filtering content out. This will pass matching
        content unconditionally even if some other filter removes
        entry.

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
        manager.register(instance=self, type="filter", keyword="unconditionally", callback=self.unconditionally, order=65536)

    def unconditionally(self, feed):
        self.filter(feed, feed.unfilter, None, 'unconditionally')     

if __name__ == "__main__":
    pass
