import logging

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('resolver')


class ResolverException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Resolver:

    def register(self, manager, parser):
        manager.register('resolver', builtin=True)
        manager.add_feed_event('resolve', before='download')
        # TODO: manager.register_feed_event(name='resolve', before='download')

    def feed_resolve(self, feed):
        # no resolves in unittest mode
        if feed.unittest: return
        self.resolve_entries(feed)

    def resolvable(self, feed, entry):
        """Return True if entry is resolvable by registered resolver."""
        for resolver in feed.manager.get_modules_by_group('resolver'):
            if resolver['instance'].resolvable(self, entry):
                return True
        return False

    def resolve(self, feed, entry):
        """Resolves given entry url. Raises ResolverException if resolve failed."""
        tries = 0
        while self.resolvable(feed, entry):
            tries += 1
            if (tries > 300):
                raise ResolverException('Resolve was left in infinite loop while resolving %s, some resolver is returning always True')
            for resolver in feed.manager.get_modules_by_group('resolver'):
                name = resolver['name']
                if resolver['instance'].resolvable(feed, entry):
                    log.debug('%s resolving %s' % (name, entry['url']))
                    try:
                        resolver['instance'].resolve(feed, entry)
                    except ResolverException, r:
                        # increase failcount
                        #count = self.shared_cache.storedefault(entry['url'], 1)
                        #count += 1
                        raise ResolverException('%s: %s' % (name, r.value))
                    except Exception, e:
                        log.exception(e)
                        raise ResolverException('%s: Internal error with url %s' % (name, entry['url']))

    def resolve_entries(self, feed):
        """Resolves all entries in feed. Since this causes many requests to sites, use with caution."""
        for entry in feed.entries:
            try:
                self.resolve(feed, entry)
            except ResolverException, e:
                log.warn(e.value)
                feed.fail(entry)

