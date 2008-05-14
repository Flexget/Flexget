import urllib
import urllib2
import urlparse
import logging
from feed import ResolverException

log = logging.getLogger('piratebay')

# this way we don't force users to install bs incase they do not want to use module
soup_present = True

try:
    from BeautifulSoup import BeautifulSoup
except:
    soup_present = False

class ResolvePirateBay:
    """PirateBay resolver."""

    def register(self, manager, parser):
        # disable module if soup is not present
        if not soup_present:
            log.info('Resolver disabled. BeautifulSoup is not installed.')
            return
        manager.register_resolver(instance=self, name='piratebay')

    def resolvable(self, feed, entry):
        url = entry['url']
        if url.startswith('http://thepiratebay.org/tor/') and not url.endswith('.torrent'):
            return True
        else:
            return False
        
    def resolve(self, feed, entry):
        try:
            page = urllib2.urlopen(entry['url'])
            soup = BeautifulSoup(page)
            tag_div = soup.find('div', attrs={'class':'download'})
            if not tag_div:
                raise ResolverException('Unable to locate download link from url %s' % entry['url'])
            tag_a = tag_div.find('a')
            torrent_url = tag_a.get('href')
            entry['url'] = torrent_url
        except Exception, e:
            raise ResolverException(e)
