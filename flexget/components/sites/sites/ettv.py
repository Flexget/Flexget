from urllib.parse import urlparse

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.event import event
from flexget.utils.soup import get_soup

logger = logger.bind(name='ettv')

DOMAINS = [
    'www.ettv.to',
    'www.ettvdl.com',
    'www.ettvcentral.com',
]


class UrlRewriteETTV:
    """ETTV urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        return urlparse(entry['url']).netloc in DOMAINS

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
        tag_a = soup.select_one('a.download_link.magnet')
        if not tag_a:
            raise UrlRewritingError(f"Unable to locate download link from url {url}")
        return tag_a.get('href')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteETTV, 'ettv', interfaces=['urlrewriter'], api_ver=2)
