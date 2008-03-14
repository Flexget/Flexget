# -*- coding: cp1252 -*-
import urllib
import urllib2
import urlparse
import logging
import re
from feed import ResolverException

log = logging.getLogger("newtorrents")

# this way we don't force users to install bs incase they do not want to use module
soup_present = True
soup_err = "Module newtorrents requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository."

try:
    from BeautifulSoup import BeautifulSoup
except:
    log.warning(soup_err)
    soup_present = False

class ResolveNewTorrents:
    """NewTorrents resolver."""

    # a bit messy since this was not originally a resolver

    def __init__(self):
        self.resolved = []

    def register(self, manager, parser):
        manager.register_resolver(instance=self, name='newtorrents')

    def resolvable(self, feed, entry):
        # Return true only for urls that can and should be resolved
        return entry['url'].startswith('http://www.newtorrents.info') and not entry['url'] in self.resolved
        
    def resolve(self, feed, entry):
        if not soup_present: raise Exception(soup_err)

        # resolve entry url
        url = entry['url']
        if url.startswith("http://www.newtorrents.info/?q=") or url.startswith("http://www.newtorrents.info/search"):
            url = self.__get_torrent_url_from_search(url, entry['title'])
        else:
            url = self.__get_torrent_url_from_page(url)

        if url:
            entry['url'] = url
            self.resolved.append(url)
        else:
            raise ResolverException('Bug in newtorrents resolver')
    
    def __get_torrent_url_from_page(self, url):
        """Parses torrent url from newtorrents download page"""
        try:
            page = urllib2.urlopen(url)
            data = page.read()
        except urllib2.URLError, e:
            log.error("URLerror when retrieving page")
            return None
        p = re.compile("copy\(\'(.*)\'\)", re.IGNORECASE)
        f = p.search(data)
        if not f:
            # the link in which module relies is missing!
            raise ResolverException('Failed to get url from download page. Module may need a update.')
        else:
            return f.groups()[0]

    def __get_torrent_url_from_search(self, url, name):
        """Parses torrent download url (requires release name) from search results"""
        name = name.replace('.',' ').lower()
        try:
            page = urllib2.urlopen(url)
        except urllib2.URLError, e:
            raise ResolverException('Timed out when opening page')
        
        soup = BeautifulSoup(page)
        torrents = []
        for link in soup.findAll('a', attrs={'href': re.compile('down.php')}):
            torrent_url = "http://www.newtorrents.info%s" % link.get('href')
            release_name = link.parent.next.get('title').replace('.',' ').lower()
            if release_name == name:
                torrents.append(torrent_url)
            else:
                log.debug("rejecting search result: '%s' != '%s'" % (release_name, name))

        # choose the torrent
        if not torrents:
            raise ResolverException('No matches in search result')
        else:
            if len(torrents) == 1:
                log.debug("found only one matching search result.")
            else:
                log.debug('search result contains multiple matches, using first occurence from: %s' % torrents)
                # TODO: use the one that has most downloaders / seeders
            return torrents[0]


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)
    import test_tools
    test_tools.test_resolver(ResolveNewTorrents())
