from __future__ import unicode_literals, division, absolute_import
import logging
import re
#import urllib2
#import urllib
import unicodedata

from flexget import plugin
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.utils import requests
from flexget.utils.soup import get_soup

from flexget.entry import Entry
from flexget.utils.search import normalize_unicode

#from flexget.manager import Session

log = logging.getLogger('elitetorrent')

#session = requests.Session()

class UrlRewriteElitetorrent(object):
    """
    elitetorrent urlrewriter and search Plugin.
    """
   
#    USER_AGENT = 'Mozilla/5.0'
    
    schema = {
        'type': 'object',
        'properties': {
            'category': {'type': 'string'},
        },
        'additionalProperties': False
    }

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        return (url.startswith('http://www.elitetorrent.net/torrent/'))

    # urlrewriter API
    def url_rewrite(self, task, entry):
        entry['url'] = self.parse_download_page(entry['url'])

    @plugin.internet(log)
    def parse_download_page(self, url):
        try:
            page = requests.get(url).content
            soup = get_soup(page, 'html.parser')
            download_link = soup.findAll(href=re.compile('/get-torrent/\d+'))
            download_href = 'http://www.elitetorrent.net' + download_link[0]['href']
            return download_href
        except Exception:
            raise UrlRewritingError(
                'Unable to locate torrent from url %s' % url
            )
	 
    def rm_tildes(self, data):
	    return unicodedata.normalize('NFKD', data).encode('ASCII', 'ignore')

    def search(self, task, entry, config=None):
        log.debug('Search elitetorrent')
        url_search = 'http://www.elitetorrent.net/buscar.php'
        task.requests.set_domain_delay('www.elitetorrent.net', '2.5 seconds') # they only allow 1 request per 2 seconds

        results = set()
        #rm year
        regex = re.compile("(.+) \(\d\d\d\d\)")
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)
            query = self.rm_tildes(regex.findall(query)[0])
            log.debug('Searching elitetorrent %s' % query)
            query = query.encode('utf8', 'ignore')
            #POST request or chaneg to "http://www.elitetorrent.net/busqueda/query+with+plus"
            data = {'buscar': query}
            try:
                response = task.requests.post(url_search, data=data)
            except requests.RequestException as e:
                log.error('Error searching elitetorrent: %s' % e)
                continue
            
            #req = urllib2.Request(url_search, data)
            #response = urllib2.urlopen(req)
            content = response.content # read()#.content
            soup = get_soup(content)
            #<a class="nombre" href="/torrent/25319/como-entrenar-a-tu-dragon-2-hdrip" title="Como entrenar a tu dragon 2 (HDRip)">Como entrenar a tu dragon 2 (HDRip)</a>
            children = soup.findAll('a', attrs={'class': 'nombre'})
            log.verbose(len(children))
            for child in children:
                entry = Entry()
                entry['url'] = 'http://www.elitetorrent.net' + child['href']
                entry['title'] = child['title']
                #log.debug(child['href'])
                results.add(entry)
        log.debug('Finish search elitetorrent with %d entries' % len(results))
        return results

@event('plugin.register')
def register_plugin():
    plugin.register(
        UrlRewriteElitetorrent,
        'elitetorrent',
        groups=['urlrewriter', 'search'],
        api_ver=2
    )
