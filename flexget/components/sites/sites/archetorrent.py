from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name="archetorrent")


class UrlRewriteArchetorrent:
    """Archetorrent urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        return url.startswith('https://www.archetorrent.com') and url.find('download') == -1

    # urlrewriter API
    def url_rewrite(self, task, entry):
        if 'url' not in entry:
            logger.error("Didn't actually get a URL...")
        else:
            logger.debug('Got the URL: {}', entry['url'])
            entry['url'] = entry['url'].replace('torrents-details', 'download')
            entry['url'] = entry['url'].replace('&hit=1', '')
            logger.debug('New URL: {}', entry['url'])


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteArchetorrent, 'archetorrent', interfaces=['urlrewriter'], api_ver=2)
