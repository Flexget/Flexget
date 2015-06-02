from __future__ import unicode_literals, division, absolute_import
import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.utils.requests import Session
from flexget.utils.soup import get_soup

log = logging.getLogger('newpct')

requests = Session()
requests.headers.update({'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'})
requests.set_domain_delay('imdb.com', '2 seconds')


class UrlRewriteNewPCT(object):
    """NewPCT urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        rewritable_regex = '^http:\/\/(www.)?newpct1?.com\/.*'
        return re.match(rewritable_regex, url) and not url.startswith('http://www.newpct.com/descargar/')

    # urlrewriter API
    def url_rewrite(self, task, entry):
        entry['url'] = self.parse_download_page(entry['url'])

    @plugin.internet(log)
    def parse_download_page(self, url):
        page = requests.get(url)
        try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(e)
        torrent_id_prog = re.compile("'(?:torrentID|id)'\s*:\s*'(\d+)'")
        torrent_ids = soup.findAll(text=torrent_id_prog)
        if len(torrent_ids) == 0:
            raise UrlRewritingError('Unable to locate torrent ID from url %s' % url)
        torrent_id = torrent_id_prog.search(torrent_ids[0]).group(1)
        return 'http://www.newpct.com/descargar/torrent/%s/dummy.html' % torrent_id


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteNewPCT, 'newpct', groups=['urlrewriter'], api_ver=2)
