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
            url.startswith('http://www.divxatope.com/descargar') or url.startswith('http://divxatope.com/descargar')
        )

    # urlrewriter API
    def url_rewrite(self, task, entry):
        # Rewrite divxatope.com/descargar/ to divxatope.com/descarga-torrent/
        entry['url'] = re.sub('/descargar', '/descarga-torrent', entry['url'])
        entry['url'] = self.parse_download_page(entry['url'])

    @plugin.internet(log)
    def parse_download_page(self, url):
        try:
            page = requests.get(url).content
            soup = get_soup(page, 'html.parser')
            download_link = soup.findAll(href=re.compile('redirect|redirectlink'))
            download_href = download_link[0]['href']
            if "url" in download_href:
                redirect_search = re.search('.*url=(.*)', download_href)
                if redirect_search:
                    redirect_link = redirect_search.group(1)
                else:
                    raise UrlRewritingError('Redirect link for %s could not be found %s' % url)
                if redirect_link.startswith('http'):
                    return redirect_link
                else:
                    return 'http://www.divxatope.com/' + redirect_link
            else:
                return download_href
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
