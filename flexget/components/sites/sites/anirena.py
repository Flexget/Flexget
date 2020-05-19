from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='anirena')


class UrlRewriteAniRena:
    """AniRena urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://www.anirena.com/viewtracker.php?action=details&id=')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('details', 'download')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteAniRena, 'anirena', interfaces=['urlrewriter'], api_ver=2)
