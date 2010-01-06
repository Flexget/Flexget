import copy
import logging
from flexget.plugin import *

log = logging.getLogger('input_cache')


class InputCache:
    """
        Utility plugin, adds caching facilities for inputs

    """

    def validator(self):
        from flexget import validator
        return validator.factory('any')

    def __init__(self):
        self.cache = {}

    def on_process_start(self, feed):
        # clear cache
        self.cache = {}

    def store(self, feed, name):
        """Store entries from :feed: in a cache for later retrieval with :name:"""
        self.cache[name] = copy.deepcopy(feed.entries)

    def is_cached(self, name):
        """Return True if there's a data in cache with :name:"""
        return name in self.cache

    def restore(self, feed, name):
        """Add Entries to :feed: from cache with :name:. Return True if added, False if not."""
        if not name in self.cache:
            return False
        count = 0
        for entry in self.cache[name]:
            fresh = copy.deepcopy(entry)
            feed.entries.append(fresh)
            count += 1
        if count > 0:
            log.info('Added %s entries from cache' % count)
            return True
        else:
            return False

register_plugin(InputCache, 'input_cache')
