from __future__ import unicode_literals, division, absolute_import
import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.utils.requests import Session
from flexget.utils.soup import get_soup

from flexget.utils.search import normalize_unicode

from requests.auth import AuthBase

log = logging.getLogger('newpct')


class NewPCTAuth(AuthBase):
    """Attaches HTTP Pizza Authentication to the given Request object."""

    def __call__(self, r):
        headers = {'user-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0'
                  }
        r.prepare_headers(headers)
        return r

class UrlRewriteNewPCT(object):
    """NewPCT urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        if entry.get('urls'):
            url = entry.get('urls')[0]
        else:
            url = entry['url']
        rewritable_regex='^http:\/\/(www.)?newpct1?.com\/.*'
        return re.match(rewritable_regex,url) and not url.startswith('http://www.newpct.com/descargar/') and not url.endswith('.torrent') and not url.startswith('http://www.newpct1.com/descargar-torrent/')

    # urlrewriter API
    def url_rewrite(self, task, entry):
        if 'newpct1' in entry['url']:
	    auth_handler = NewPCTAuth()
            entry['download_auth'] = auth_handler
            entry['urls'] = [self.parse_download_page_newpct1(task, entry['url'])]
        else:
            entry['urls'] = [self.parse_download_page(task, entry['url'])]
        task.requests = Session() 
    
    def parse_download_page_newpct1(self, task, url):
        log.verbose('URL newpct1')
        log.debug(url)
        url = url.replace('newpct1.com/', 'newpct1.com/descarga-torrent/')
        page = task.requests.get(url).content
        soup = get_soup(page)
        regex = re.compile(r'http:\/\/tumejorjuego\.com\/download\/index\.php\?link=descargar-torrent\/.+')
        query = soup.findAll('a', href = regex)
        if len(query) == 0:
            raise UrlRewritingError('Unable to locate torrent from url %s' % url)
        url = query[0]['href']
        url = url.replace('http://tumejorjuego.com/download/index.php?link=', 'http://www.newpct1.com/')
        return url

    @plugin.internet(log)
    def parse_download_page(self, task, url):
        log.verbose('URL newpct')
        log.debug(url)
        page = task.requests.get(url)
        try:
            soup = get_soup(page.content)
        except Exception as e:
            raise UrlRewritingError(e)
        torrent_span = soup.find('span', attrs={'id': 'content-torrent'})
        try:
            torrent_tag = torrent_span.findAll('a', href=True)
        except Exception as e:
            log.error('Error findAll')
        if len(torrent_tag) == 0:
            raise UrlRewritingError('Unable to locate torrent from url %s' % url)
        return torrent_tag[0]['href']

    def remove_parentheses(self, result):
        result = re.sub('[()]', ' ', result)
        return result

@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteNewPCT, 'newpct', groups=['urlrewriter'], api_ver=2)
