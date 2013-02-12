from __future__ import unicode_literals, division, absolute_import
import urllib2
import logging
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.plugin import register_plugin, internet
from flexget.utils.tools import urlopener
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
        entry['url'] = self.parse_download_page(entry['url'])

    @internet(log)
    def parse_download_page(self, url):
        txheaders = {'User-agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        req = urllib2.Request(url, None, txheaders)
        page = urlopener(req, log)
        try:
            soup = get_soup(page)
        except Exception as e:
            raise UrlRewritingError(e)
        tag_a = soup.find('a', attrs={'class': 'download_link'})
        if not tag_a:
            raise UrlRewritingError('Unable to locate download link from url %s' % url)
        torrent_url = 'http://www.bakabt.com' + tag_a.get('href')
        return torrent_url

register_plugin(UrlRewriteBakaBT, 'bakabt', groups=['urlrewriter'])
