from __future__ import unicode_literals, division, absolute_import
import logging
import re
import urllib2

from flexget import plugin
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.utils.tools import urlopener
from flexget.utils.soup import get_soup

log = logging.getLogger('deadfrog')


class UrlRewriteDeadFrog(object):
    """DeadFrog urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('http://www.deadfrog.us/download/'):
            return False
        if url.startswith('http://www.deadfrog.us/') or url.startswith('http://deadfrog.us/'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        entry['url'] = self.parse_download_page(entry['url'])

    @plugin.internet(log)
    def parse_download_page(self, url):
        txheaders = {'User-agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        req = urllib2.Request(url, None, txheaders)
        page = urlopener(req, log)
        try:
            soup = get_soup(page)
        except Exception as e:
            raise UrlRewritingError(e)
        down_link = soup.find('a', attrs={'href': re.compile("download/\d+/.*\.torrent")})
        if not down_link:
            raise UrlRewritingError('Unable to locate download link from url %s' % url)
        return 'http://www.deadfrog.us/' + down_link.get('href')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteDeadFrog, 'deadfrog', groups=['urlrewriter'], api_ver=2)
