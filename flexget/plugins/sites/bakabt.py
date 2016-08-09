from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError
from flexget.utils.soup import get_soup

log = logging.getLogger('bakabt')


class UrlRewriteBakaBT(object):
    """BakaBT urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('http://www.bakabt.com/download/'):
            return False
        if url.startswith('http://www.bakabt.com/') or url.startswith('http://bakabt.com/'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        entry['url'] = self.parse_download_page(entry['url'], task.requests)

    @plugin.internet(log)
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
        torrent_url = 'http://www.bakabt.com' + tag_a.get('href')
        return torrent_url


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteBakaBT, 'bakabt', groups=['urlrewriter'], api_ver=2)
