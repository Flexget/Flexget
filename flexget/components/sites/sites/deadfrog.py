import re

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.event import event
from flexget.utils.soup import get_soup

logger = logger.bind(name='deadfrog')


class UrlRewriteDeadFrog:
    """DeadFrog urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('http://www.deadfrog.us/download/'):
            return False
        return bool(url.startswith(('http://www.deadfrog.us/', 'http://deadfrog.us/')))

    # urlrewriter API
    def url_rewrite(self, task, entry):
        entry['url'] = self.parse_download_page(entry['url'], task.requests)

    @plugin.internet(logger)
    def parse_download_page(self, url, requests):
        txheaders = {'User-agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        page = requests.get(url, headers=txheaders)
        try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(e)
        down_link = soup.find('a', attrs={'href': re.compile(r'download/\d+/.*\.torrent')})
        if not down_link:
            raise UrlRewritingError(f'Unable to locate download link from url {url}')
        return 'http://www.deadfrog.us/' + down_link.get('href')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteDeadFrog, 'deadfrog', interfaces=['urlrewriter'], api_ver=2)
