import urllib2
import logging
import re
from module_resolver import ResolverException
from manager import ModuleWarning

timeout = 10
import socket
socket.setdefaulttimeout(timeout)

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger('newtorrents')

# this way we don't force users to install bs incase they do not want to use module
soup_present = True
try:
    from BeautifulSoup import BeautifulSoup
except:
    soup_present = False
    
class NewTorrents:
    """NewTorrents resolver and search module."""

    def __init__(self):
        self.resolved = []

    def register(self, manager, parser):
        manager.register('newtorrents', groups=['resolver', 'search'])

    # Resolver module API
    def resolvable(self, feed, entry):
        # Return true only for urls that can and should be resolved
        return entry['url'].startswith('http://www.newtorrents.info') and not entry['url'] in self.resolved
        
    # Resolver module API
    def resolve(self, feed, entry):
        if not soup_present:
            raise ResolverException('BeautifulSoup not present')

        # resolve entry url
        url = entry['url']
        if url.startswith('http://www.newtorrents.info/?q=') or url.startswith('http://www.newtorrents.info/search'):
            try:
                url = self.url_from_search(url, entry['title'])
            except ModuleWarning, e:
                raise ResolverException(e)
        else:
            url = self.url_from_page(url)

        if url:
            entry['url'] = url
            self.resolved.append(url)
        else:
            raise ResolverException('Bug in newtorrents resolver')
            
    # Search module API
    def search(self, feed, entry):
        import urllib
        search_url = 'http://www.newtorrents.info/search/%s' % urllib.quote(entry['title'])
        url = self.url_from_search(search_url, entry['title'])
        entry['url'] = url
    
    def url_from_page(self, url):
        """Parses torrent url from newtorrents download page"""
        try:
            page = urllib2.urlopen(url)
            data = page.read()
        except urllib2.URLError:
            raise ResolverException('URLerror when retrieving page')
        p = re.compile("copy\(\'(.*)\'\)", re.IGNORECASE)
        f = p.search(data)
        if not f:
            # the link in which module relies is missing!
            raise ResolverException('Failed to get url from download page. Module may need a update.')
        else:
            return f.group(1)

    def url_from_search(self, url, name):
        """Parses torrent download url from search results"""
        name = name.replace('.',' ').lower()
        try:
            html = urllib2.urlopen(url).read()
            # fix </SCR'+'IPT> so that BS does not crash
            html = re.sub(r'(</SCR.*?)...(.*?IPT>)', r'\1\2', html)
        except urllib2.URLError:
            raise ModuleWarning('Timed out when opening search page', log)
        
        soup = BeautifulSoup(html)
        torrents = []
        for link in soup.findAll('a', attrs={'href': re.compile('down.php')}):
            torrent_url = 'http://www.newtorrents.info%s' % link.get('href')
            release_name = link.parent.next.get('title').replace('.',' ').lower()
            if release_name == name:
                torrents.append(torrent_url)
            else:
                log.debug('rejecting search result: %s != %s' % (release_name, name))

        # choose the torrent
        if not torrents:
            raise ModuleWarning('No matches for %s' % name, log, log_once=True)
        else:
            if len(torrents) == 1:
                log.debug('found only one matching search result.')
            else:
                log.debug('search result contains multiple matches, using first occurence from: %s' % torrents)
                # TODO: use the one that has most downloaders / seeders
            return torrents[0]