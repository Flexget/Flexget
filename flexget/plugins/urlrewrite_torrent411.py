# coding: utf-8
from __future__ import unicode_literals, division, absolute_import
import re
import logging

from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.plugin import internet, register_plugin
from flexget.utils.tools import urlopener
from flexget.utils.soup import get_soup

log = logging.getLogger('torrent411')


class UrlRewriteTorrent411(object):
    """torrent411 RSS url_rewrite"""

    def url_rewritable(self, feed, entry):
        url = entry['url']
        # match si ce qui suit 'http://www.t411.me/torrents/' ne contient pas
        # '/' comme 'http://www.t411.me/torrents/browse/...' ou
        # 'http://www.t411.me/torrents/download/...'
        if re.match(r'^http://www\.t411\.me/torrents/[^/]+(?!/)[^/]+$', url):
            return True
        return False

    def url_rewrite(self, feed, entry):
        old_url = entry['url']
        entry['url'] = self.parse_download_page(entry['url'])
        log.debug('%s rewritten to %s' % (old_url, entry['url']))

    @internet(log)
    def parse_download_page(self, url):
        page = urlopener(url, log)
        log.debug('%s opened', url)
        try:
            soup = get_soup(page)
            torrent_url = 'http://www.t411.me' + soup.find(text='Télécharger').findParent().get('href')
        except Exception, e:
            raise UrlRewritingError(e)

        if not torrent_url:
            raise UrlRewritingError('Unable to locate download link from url %s' % url)

        return torrent_url

register_plugin(UrlRewriteTorrent411, 'torrent411', groups=['urlrewriter'])
