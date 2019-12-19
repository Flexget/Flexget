from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.event import event
from flexget.utils.soup import get_soup

logger = logger.bind(name='bakabt')


class UrlRewriteBakaBT:
    """BakaBT urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('https://bakabt.me/download/'):
            return False
        if url.startswith('https://www.bakabt.me/') or url.startswith('https://bakabt.me/'):
            return True
        return False

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
        tag_a = soup.find('a', attrs={'class': 'download_link'})
        if not tag_a:
            raise UrlRewritingError('Unable to locate download link from url %s' % url)
        torrent_url = 'https://bakabt.me/' + tag_a.get('href')
        return torrent_url


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteBakaBT, 'bakabt', interfaces=['urlrewriter'], api_ver=2)
