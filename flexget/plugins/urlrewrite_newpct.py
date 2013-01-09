from __future__ import unicode_literals, division, absolute_import
import urllib2
import logging
import re

from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.plugin import register_plugin, internet
from flexget.utils.tools import urlopener
from flexget.utils.soup import get_soup

log = logging.getLogger('newpct')


class UrlRewriteNewPCT(object):
    """NewPCT urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('http://www.newpct.com/download/'):
            return False
        if url.startswith('http://www.newpct.com/') or url.startswith('http://newpct.com/'):
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
        except Exception, e:
            raise UrlRewritingError(e)
        down_link = soup.find('a', attrs={'href': re.compile("descargar/torrent/")})
        if not down_link:
            raise UrlRewritingError('Unable to locate download link from url %s' % url)
        return down_link.get('href')


register_plugin(UrlRewriteNewPCT, 'newpct', groups=['urlrewriter'])
