import logging
from flexget.plugin import *

log = logging.getLogger('resolver')

class ResolverException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class PluginResolver:
    def on_feed_resolve(self, feed):
        # no resolves in unit test mode
        if feed.manager.unit_test: 
            return
        self.entries(feed)

    def resolvable(self, feed, entry):
        """Return True if entry is resolvable by registered resolver."""
        for resolver in get_plugins_by_group('resolver'):
            if resolver.instance.resolvable(self, entry):
                return True
        return False

    def resolve(self, feed, entry):
        """Resolves given entry url. Raises ResolverException if resolve failed."""
        tries = 0
        while self.resolvable(feed, entry):
            tries += 1
            if (tries > 300):
                raise ResolverException('Resolve was left in infinite loop while resolving %s, some resolver is returning always True' % entry)
            for resolver in get_plugins_by_group('resolver'):
                name = resolver.name
                try:
                    if resolver.instance.resolvable(feed, entry):
                        log.debug('Rerolving %s' % entry['url'])
                        resolver.instance.resolve(feed, entry)
                        log.info('Resolved \'%s\' to %s (with %s)' % (entry['title'], entry['url'], name))
                except ResolverException, r:
                    # increase failcount
                    #count = self.shared_cache.storedefault(entry['url'], 1)
                    #count += 1
                    raise ResolverException('Resolver %s failed: %s' % (name, r.value))
                except Exception, e:
                    log.exception(e)
                    raise ResolverException('%s: Internal error with url %s' % (name, entry['url']))

    def entries(self, feed):
        """Resolves all accepted entries in feed. Since this causes many requests to sites, use with caution."""
        for entry in feed.accepted:
            try:
                self.resolve(feed, entry)
            except ResolverException, e:
                log.warn(e.value)
                feed.fail(entry)

register_plugin(PluginResolver, 'resolver', builtin=True, priorities={'resolve': 255})
register_feed_event(PluginResolver, 'resolve', before='download')
