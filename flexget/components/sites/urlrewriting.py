from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='urlrewriter')


class UrlRewritingError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class PluginUrlRewriting:
    """
    Provides URL rewriting framework
    """

    def __init__(self):
        self.disabled_rewriters = []

    def on_task_urlrewrite(self, task, config):
        logger.debug('Checking {} entries', len(task.accepted))
        # try to urlrewrite all accepted
        for entry in task.accepted:
            try:
                self.url_rewrite(task, entry)
            except UrlRewritingError as e:
                logger.warning(e.value)
                entry.fail()

    # API method
    def url_rewritable(self, task, entry):
        """Return True if entry is urlrewritable by registered rewriter."""
        for urlrewriter in plugin.get_plugins(interface='urlrewriter'):
            if urlrewriter.name in self.disabled_rewriters:
                logger.trace("Skipping rewriter {} since it's disabled", urlrewriter.name)
                continue
            logger.trace('checking urlrewriter {}', urlrewriter.name)
            if urlrewriter.instance.url_rewritable(task, entry):
                return True
        return False

    # API method - why priority though?
    @plugin.priority(plugin.PRIORITY_FIRST)
    def url_rewrite(self, task, entry):
        """Rewrites given entry url. Raises UrlRewritingError if failed."""
        tries = 0
        while self.url_rewritable(task, entry) and entry.accepted:
            tries += 1
            if tries > 20:
                raise UrlRewritingError(
                    'URL rewriting was left in infinite loop while rewriting url for %s, '
                    'some rewriter is returning always True' % entry
                )
            for urlrewriter in plugin.get_plugins(interface='urlrewriter'):
                name = urlrewriter.name
                if name in self.disabled_rewriters:
                    logger.trace("Skipping rewriter {} since it's disabled", name)
                    continue
                try:
                    if urlrewriter.instance.url_rewritable(task, entry):
                        old_url = entry['url']
                        logger.debug('Url rewriting {}', entry['url'])
                        urlrewriter.instance.url_rewrite(task, entry)
                        if entry['url'] != old_url:
                            if entry.get('urls') and old_url in entry.get('urls'):
                                entry['urls'][entry['urls'].index(old_url)] = entry['url']
                            logger.info(
                                "Entry '{}' URL rewritten to {} (with {})",
                                entry['title'],
                                entry['url'],
                                name,
                            )
                except UrlRewritingError as r:
                    # increase failcount
                    # count = self.shared_cache.storedefault(entry['url'], 1)
                    # count += 1
                    raise UrlRewritingError('URL rewriting %s failed: %s' % (name, r.value))
                except plugin.PluginError as e:
                    raise UrlRewritingError('URL rewriting %s failed: %s' % (name, e.value))
                except Exception as e:
                    logger.exception(e)
                    raise UrlRewritingError(
                        '%s: Internal error with url %s' % (name, entry['url'])
                    )


class DisableUrlRewriter:
    """Disable certain urlrewriters."""

    schema = {'type': 'array', 'items': {'type': 'string'}}

    def on_task_start(self, task, config):
        urlrewriting = plugin.get('urlrewriting', self)
        for disable in config:
            try:
                plugin.get(disable, self)
            except plugin.DependencyError:
                logger.critical('Unknown url-rewriter {}', disable)
                continue
            logger.debug('Disabling url rewriter {}', disable)
            urlrewriting.disabled_rewriters.append(disable)

    def on_task_exit(self, task, config):
        urlrewriting = plugin.get('urlrewriting', self)
        for disable in config:
            logger.debug('Enabling url rewriter {}', disable)
            try:
                urlrewriting.disabled_rewriters.remove(disable)
            except ValueError:
                logger.debug('{} does not exists', disable)

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(PluginUrlRewriting, 'urlrewriting', builtin=True, api_ver=2)
    plugin.register(DisableUrlRewriter, 'disable_urlrewriters', api_ver=2)

    plugin.register_task_phase('urlrewrite', before='download')
