from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.soup import get_soup

log = logging.getLogger('newpct')

requests = Session()
requests.headers.update({'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'})
requests.add_domain_limiter(TimedLimiter('imdb.com', '2 seconds'))


class UrlRewriteNewPCT(object):
    """NewPCT urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        rewritable_regex = '^http:\/\/(www.)?newpct1?.com\/.*'
        return re.match(rewritable_regex, url) and not url.endswith('.torrent')

    # urlrewriter API
    def url_rewrite(self, task, entry):
        entry['url'] = self.parse_download_page(entry['url'])

    @plugin.internet(log)
    def parse_download_page(self, url):
        if 'newpct1.com' in url:
            log.verbose('Newpct1 URL: %s', url)
            url = url.replace('newpct1.com/', 'newpct1.com/descarga-torrent/')
        else:
            log.verbose('Newpct URL: %s', url)

        try:
            page = requests.get(url)
        except requests.exceptions.RequestException as e:
            raise UrlRewritingError(e)
        try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(e)

        if 'newpct1.com' in url:
            torrent_id_prog = re.compile(r'descargar-torrent/(.+)/')
            torrent_ids = soup.findAll(href=torrent_id_prog)
        else:
            torrent_id_prog = re.compile("'(?:torrentID|id)'\s*:\s*'(\d+)'")
            torrent_ids = soup.findAll(text=torrent_id_prog)

        if len(torrent_ids) == 0:
            raise UrlRewritingError('Unable to locate torrent ID from url %s' % url)

        if 'newpct1.com' in url:
            torrent_id = torrent_id_prog.search(torrent_ids[0]['href']).group(1)
            return 'http://www.newpct1.com/download/%s.torrent' % torrent_id
        else:
            torrent_id = torrent_id_prog.search(torrent_ids[0]).group(1)
            return 'http://www.newpct.com/torrents/{:0>6}.torrent'.format(torrent_id)


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteNewPCT, 'newpct', groups=['urlrewriter'], api_ver=2)
