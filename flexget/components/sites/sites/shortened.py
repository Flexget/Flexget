from urllib.parse import urlparse

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='shortened')


class UrlRewriteShortened:
    """Shortened url rewriter."""

    def url_rewritable(self, task, entry):
        return urlparse(entry['url']).netloc in ['bit.ly', 't.co']

    def url_rewrite(self, task, entry):
        request = task.requests.head(entry['url'], allow_redirects=True)
        entry['url'] = request.url


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteShortened, 'shortened', interfaces=['urlrewriter'], api_ver=2)
