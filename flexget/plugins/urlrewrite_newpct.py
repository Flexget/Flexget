from __future__ import unicode_literals, division, absolute_import
import logging
import os
import re
import urllib2
from urlparse import urlparse

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
        torrent_id_prog = re.compile("'torrentID': '(\d+)'")
        torrent_ids = soup.findAll(text=torrent_id_prog)
        if len(torrent_ids) == 0:
            raise UrlRewritingError('Unable to locate torret ID from url %s' % url)
        torrent_id = torrent_id_prog.search(torrent_ids[0]).group(1)
        return 'http://www.pctorrent.com/descargar/index.php?link=descargar/torrent/%s/dummy.html' % torrent_id

register_plugin(UrlRewriteNewPCT, 'newpct', groups=['urlrewriter'])
