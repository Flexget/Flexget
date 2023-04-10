import re

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.event import event
from flexget.utils.soup import get_soup

logger = logger.bind(name='hliang')


class UrlRewriteHliang:
    """Hliang urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('http://bt.hliang.com/show-'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        entry['url'] = self.parse_download_page(entry['url'], task.requests)

    @plugin.internet(logger)
    def parse_download_page(self, url, requests):
        txheaders = {'User-agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        try:
            page = requests.get(url, headers=txheaders)
        except requests.exceptions.RequestException as e:
            msg = f'Cannot open "{url}" : {str(e)}'
            logger.error(msg)
            raise UrlRewritingError(msg)

        try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(str(e))

        down_link = soup.find('a', attrs={'href': re.compile(r"down\.php\?.*")})
        if not down_link:
            raise UrlRewritingError('Unable to locate download link from url "%s"' % url)
        return 'http://bt.hliang.com/' + down_link.get('href')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteHliang, 'hliang', interfaces=['urlrewriter'], api_ver=2)
