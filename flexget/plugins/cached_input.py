import copy
import logging
from flexget.plugin import *

log = logging.getLogger('cached')


class cached(object):

    """
    Implements transparent caching decorator @cached for inputs.

    Decorator has two parameters

    :name: in which the configuration is present in feeds configuration.
    :key: in which the configuration has the cached resource identifier (ie. url). If the :key: is not
    given or present in the configuration :name: is expected to be a cache name (ie. url)

    Configuration assumptions may make this unusable in some (future) inputs
    """

    cache = {}

    def __init__(self, name, key=None):
        self.name = name
        self.key = key

    def __call__(self, func):

        def wrapped_func(*args, **kwargs):

            # get feed from method parameters
            feed = args[1]

            # get name for a cache from feeds configuration
            if not self.name in feed.config:
                raise Exception('@cache config name %s is not configured in feed %s' % (self.name, feed.name))
            config = feed.config[self.name]

            log.log(5, 'config: %s' % config)
            log.log(5, 'self.name: %s' % self.name)
            log.log(5, 'self.key: %s' % self.key)

            if isinstance(config, dict) and self.key in config:
                name = feed.config[self.name][self.key]
            else:
                name = feed.config[self.name]

            log.debug('cache name: %s (has: %s)' % (name, ', '.join(self.cache.keys())))

            if name in self.cache:
                log.log(5, 'cache hit')
                count = 0
                for entry in self.cache[name]:
                    fresh = copy.deepcopy(entry)
                    feed.entries.append(fresh)
                    count += 1
                if count > 0:
                    feed.verbose_progress('Restored %s entries from cache' % count, log)
            else:
                log.log(5, 'cache miss')
                # call input event
                func(*args, **kwargs)
                # store results to cache
                log.debug('storing to cache %s %s entries' % (name, len(feed.entries)))
                self.cache[name] = copy.deepcopy(feed.entries)

        return wrapped_func


class CacheClearer:

    def on_process_start(self, feed):
        """Internal. Clears the input cache on every process"""
        # as flexget runs only once process per run this is not necessary,
        # will be needed in the future tough
        global cache
        cache = {}

register_plugin(CacheClearer, 'cache_clearer', builtin=True)
