from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import get_plugins_by_group, priority, PluginError, register_plugin, register_task_phase

log = logging.getLogger('urlrewriter')


class UrlRewritingError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class PluginUrlRewriting(object):
    """
    Provides URL rewriting framework
    """

    def on_task_urlrewrite(self, task):
        log.debug('Checking %s entries' % len(task.accepted))
        # try to urlrewrite all accepted
        for entry in task.accepted:
            try:
                self.url_rewrite(task, entry)
            except UrlRewritingError as e:
                log.warn(e.value)
                task.fail(entry)

    def url_rewritable(self, task, entry):
        """Return True if entry is urlrewritable by registered rewriter."""
        for urlrewriter in get_plugins_by_group('urlrewriter'):
            log.trace('checking urlrewriter %s' % urlrewriter.name)
            if urlrewriter.instance.url_rewritable(self, entry):
                return True
        return False

    @priority(255)
    def url_rewrite(self, task, entry):
        """Rewrites given entry url. Raises UrlRewritingError if failed."""
        tries = 0
        while self.url_rewritable(task, entry):
            tries += 1
            if tries > 300:
                raise UrlRewritingError('URL rewriting was left in infinite loop while rewriting url for %s, some rewriter is returning always True' % entry)
            for urlrewriter in get_plugins_by_group('urlrewriter'):
                name = urlrewriter.name
                try:
                    if urlrewriter.instance.url_rewritable(task, entry):
                        log.debug('Url rewriting %s' % entry['url'])
                        urlrewriter.instance.url_rewrite(task, entry)
                        log.info('Entry \'%s\' URL rewritten to %s (with %s)' % (entry['title'], entry['url'], name))
                except UrlRewritingError as r:
                    # increase failcount
                    #count = self.shared_cache.storedefault(entry['url'], 1)
                    #count += 1
                    raise UrlRewritingError('URL rewriting %s failed: %s' % (name, str(r.value)))
                except PluginError as e:
                    raise UrlRewritingError('URL rewriting %s failed: %s' % (name, str(e.value)))
                except Exception as e:
                    log.exception(e)
                    raise UrlRewritingError('%s: Internal error with url %s' % (name, entry['url']))

register_plugin(PluginUrlRewriting, 'urlrewriting', builtin=True)
register_task_phase('urlrewrite', before='download')
