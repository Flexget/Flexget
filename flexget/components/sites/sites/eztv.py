import re
from urllib.parse import urlparse, urlunparse

from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.event import event
from flexget.utils.soup import get_soup

logger = logger.bind(name='eztv')

EZTV_MIRRORS = [('http', 'eztv.ch'), ('https', 'eztv-proxy.net'), ('http', 'eztv.come.in')]


class UrlRewriteEztv:
    """Eztv url rewriter."""

    def url_rewritable(self, task, entry):
        return urlparse(entry['url']).netloc == 'eztv.ch'

    def url_rewrite(self, task, entry):
        url = entry['url']
        page = None
        for scheme, netloc in EZTV_MIRRORS:
            try:
                _, _, path, params, query, fragment = urlparse(url)
                url = urlunparse((scheme, netloc, path, params, query, fragment))
                page = task.requests.get(url).content
            except RequestException:
                logger.debug('Eztv mirror `{}` seems to be down', url)
                continue
            break

        if not page:
            raise UrlRewritingError('No mirrors found for url %s' % entry['url'])

        logger.debug('Eztv mirror `{}` chosen', url)
        try:
            soup = get_soup(page)
            mirrors = soup.find_all('a', attrs={'class': re.compile(r'download_\d')})
        except Exception as e:
            raise UrlRewritingError(e)

        logger.debug('{} torrent mirrors found', len(mirrors))

        if not mirrors:
            raise UrlRewritingError('Unable to locate download link from url %s' % url)

        entry['urls'] = [m.get('href') for m in mirrors]
        entry['url'] = mirrors[0].get('href')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteEztv, 'eztv', interfaces=['urlrewriter'], api_ver=2)
