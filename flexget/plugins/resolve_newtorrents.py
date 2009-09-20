import urllib2
import logging
import re
from module_resolver import ResolverException
from flexget.plugin import *
from flexget.utils.soup import get_soup

timeout = 10
import socket
socket.setdefaulttimeout(timeout)

log = logging.getLogger('newtorrents')

class NewTorrents:
    """NewTorrents resolver and search plugin."""

    def __init__(self):
        self.resolved = []

    # Resolver plugin API
    def resolvable(self, feed, entry):
        # Return true only for urls that can and should be resolved
        return entry['url'].startswith('http://www.newtorrents.info') and not entry['url'] in self.resolved
        
    # Resolver plugin API
    def resolve(self, feed, entry):
        url = entry['url']
        if url.startswith('http://www.newtorrents.info/?q=') or \
           url.startswith('http://www.newtorrents.info/search'):
            try:
                url = self.url_from_search(url, entry['title'])
            except PluginWarning, e:
                raise ResolverException(e)
        else:
            url = self.url_from_page(url)

        if url:
            entry['url'] = url
            self.resolved.append(url)
        else:
            raise ResolverException('Bug in newtorrents resolver')
            
    # Search plugin API
    def search(self, feed, entry):
        search_url = 'http://www.newtorrents.info/search/%s' % entry['title']
        return self.url_from_search(search_url, entry['title'])
    
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
            # the link in which plugin relies is missing!
            raise ResolverException('Failed to get url from download page. Plugin may need a update.')
        else:
            return f.group(1)
            
    def clean(self, s):
        """Formalize names"""
        return s.replace('.',' ').replace('_',' ').strip().lower()

    def url_from_search(self, url, name):
        """Parses torrent download url from search results"""
        name = self.clean(name)
        import urllib
        url = urllib.quote(url, safe=':/~?=&%')
        log.debug('search url: %s' % url)
        try:
            html = urllib2.urlopen(url).read()
            # fix </SCR'+'IPT> so that BS does not crash
            # TODO: should use beautifulsoup massage
            html = re.sub(r'(</SCR.*?)...(.*?IPT>)', r'\1\2', html)
        except IOError, e:
            if hasattr(e, 'reason'):
                raise PluginWarning('Failed to reach server. Reason: %s' % e.reason, log)
            elif hasattr(e, 'code'):
                raise PluginWarning('The server couldn\'t fulfill the request. Error code: %s' % e.code, log)
        
        soup = get_soup(html)
        # saving torrents in dict
        torrents = []
        seeds = []
        for link in soup.findAll('a', attrs={'href': re.compile('down.php')}):
            torrent_url = 'http://www.newtorrents.info%s' % link.get('href')
            release_name = self.clean(link.parent.next.get('title'))
            # quick dirty hack
            seed = link.findNext('td', attrs={'class': re.compile('s')}).renderContents()
            if release_name == name:
                torrents.append(torrent_url)
                seeds.append(seed)
            else:
                log.debug('rejecting search result: %s != %s' % (release_name, name))
        # sort with seed number Reverse order
        torrents = [(seeds[i],torrents[i]) for i in range(len(torrents)) ]
        torrents.sort(lambda x, y: y-x)
        # choose the torrent
        if not torrents:
            raise PluginWarning('No matches for %s' % name, log, log_once=True)
        else:
            if len(torrents) == 1:
                log.debug('found only one matching search result.')
            else:
                log.debug('search result contains multiple matches, using most seeders from: %s' % torrents)
            return torrents[0][1]

register_plugin(NewTorrents, 'newtorrents', groups=['resolver', 'search'])
