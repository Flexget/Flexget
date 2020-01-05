from bs4 import BeautifulSoup
from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils import requests

logger = logger.bind(name='nnm-club')


class UrlRewriteNnmClub:
    """Nnm-club.me urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://nnm-club.me/forum/viewtopic.php?t=')

    def url_rewrite(self, task, entry):
        try:
            r = task.requests.get(entry['url'])
        except requests.RequestException as e:
            logger.error('Error while fetching page: {}', e)
            entry['url'] = None
            return
        html = r.content
        soup = BeautifulSoup(html)
        links = soup.findAll('a', href=True)
        magnets = [x for x in links if x.get('href').startswith('magnet')]
        if not magnets:
            logger.error('There is no magnet links on page ({})', entry['url'])
            entry['url'] = None
            return
        entry['url'] = magnets[0]


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteNnmClub, 'nnm-club', interfaces=['urlrewriter'], api_ver=2)
