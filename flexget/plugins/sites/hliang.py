from __future__ import unicode_literals, division, absolute_import

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError
from flexget.utils.soup import get_soup

log = logging.getLogger('hliang')

class UrlRewriteHliang(object):
    """Hliang urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('http://bt.hliang.com/show.php'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        entry['url'] = self.parse_download_page(entry['url'], task.requests)

    @plugin.internet(log)
    def parse_download_page(self, url, requests):
        txheaders = {'User-agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        try:
            page = requests.get(url, headers=txheaders)
        except requests.exceptions.RequestException as e:
            msg = 'Cannot open "%s" : %s'% (url, str(e))
            log.error(msg)
            raise UrlRewritingError(msg)

        try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(str(e))
        
        down_link = soup.find('a', attrs={'href': re.compile("down\.php\?.*")})
        if not down_link:
            raise UrlRewritingError('Unable to locate download link from url "%s"' % url)
        return 'http://bt.hliang.com/' + down_link.get('href')

@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteHliang, 'hliang', interfaces=['urlrewriter'], api_ver=2)

