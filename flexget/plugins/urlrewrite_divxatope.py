from __future__ import unicode_literals, division, absolute_import
import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.utils import requests
from flexget.utils.soup import get_soup

log = logging.getLogger('divxatope')


class UrlRewriteDivxATope(object):
    """divxatope urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        return (
            url.startswith('http://www.divxatope.com/descargar_torrent')
            or url.startswith('http://divxatope.com/descargar_torrent')
        )

    # urlrewriter API
    def url_rewrite(self, task, entry):
        entry['url'] = self.parse_download_page(entry['url'])

    @plugin.internet(log)
    def parse_download_page(self, url):
        try:
            page = requests.get(url).content
            soup = get_soup(page, 'html.parser')
            download_link = soup.findAll(href=re.compile('redirect.php'))
            download_href = download_link[0]['href']
            return download_href[download_href.index('url=') + 4:]
        except Exception:
            raise UrlRewritingError(
                'Unable to locate torrent from url %s' % url
            )


@event('plugin.register')
def register_plugin():
    plugin.register(
        UrlRewriteDivxATope,
        'divxatope',
        groups=['urlrewriter'],
        api_ver=2
    )
