import logging
from flexget.plugin import *

log = logging.getLogger('urlrewriter')


class UrlRewritingError(Exception):

    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)


class PluginUrlRewriting:

    """
    Provides URL rewriting framework
    """

    def on_feed_urlrewrite(self, feed):
        # no urlrewriting in unit test mode
        if feed.manager.unit_test: 
            return
        log.debug('Checking %s entries' % len(feed.accepted))
        # try to urlrewrite all accepted
        for entry in feed.accepted:
            try:
                self.url_rewrite(feed, entry)
            except UrlRewritingError, e:
                log.warn(e.value)
                feed.fail(entry)

    def url_rewritable(self, feed, entry):
        """Return True if entry is urlrewritable by registered rewriter."""
        for urlrewriter in get_plugins_by_group('urlrewriter'):
            log.log(5, 'checking urlrewriter %s' % urlrewriter.name)
            if urlrewriter.instance.url_rewritable(self, entry):
                return True
        return False

    def url_rewrite(self, feed, entry):
        """Rewrites given entry url. Raises UrlRewritingError if failed."""
        tries = 0
        while self.url_rewritable(feed, entry):
            tries += 1
            if (tries > 300):
                raise UrlRewritingError('URL rewriting was left in infinite loop while rewriting url for %s, some rewriter is returning always True' % entry)
            for urlrewriter in get_plugins_by_group('urlrewriter'):
                name = urlrewriter.name
                try:
                    if urlrewriter.instance.url_rewritable(feed, entry):
                        log.debug('Url rewriting %s' % entry['url'])
                        urlrewriter.instance.url_rewrite(feed, entry)
                        log.info('Entry \'%s\' URL rewritten to %s (with %s)' % (entry['title'], entry['url'], name))
                except UrlRewritingError, r:
                    # increase failcount
                    #count = self.shared_cache.storedefault(entry['url'], 1)
                    #count += 1
                    raise UrlRewritingError('URL rewriting %s failed: %s' % (name, r.value))
                except PluginError, e:
                    raise UrlRewritingError('URL rewriting %s failed: %s' % (name, e.value))
                except Exception, e:
                    log.exception(e)
                    raise UrlRewritingError('%s: Internal error with url %s' % (name, entry['url']))

register_plugin(PluginUrlRewriting, 'urlrewriting', builtin=True, priorities={'urlrewrite': 255})
register_feed_event(PluginUrlRewriting, 'urlrewrite', before='download')
