from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError
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
        entry['url'] = self.parse_download_page(entry['url'], task.requests)

    @plugin.internet(log)
    def parse_download_page(self, url, requests):
        txheaders = {'User-agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        page = requests.get(url, headers=txheaders)
        try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(e)
        down_link = soup.find('a', attrs={'href': re.compile("download/\d+/.*\.torrent")})
        if not down_link:
            raise UrlRewritingError('Unable to locate download link from url %s' % url)
        return 'http://www.deadfrog.us/' + down_link.get('href')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteDeadFrog, 'deadfrog', interfaces=['urlrewriter'], api_ver=2)
