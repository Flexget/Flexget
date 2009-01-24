import urllib, urllib2
from BeautifulSoup import BeautifulSoup
import logging

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger("newzleech")

class ResolveNewzleech:
    """
        Resolver or search by using newzleech.com
        TODO: implement resolving
    """

    def register(self, manager, parser):
        manager.register('resolve_newzleech', group='search')

    # Search API
    def search(self, feed, entry):
        url = u'http://newzleech.com/?' + urllib.urlencode({'q':entry['title'].encode('latin1'), 'group':'', 'min':'', 'max':'', 'age':''})
        log.debug('search url: %s' % url)
        
        # TODO: error handling!
        page = urllib2.urlopen(url)
        
        soup = BeautifulSoup(page)
        
        for item in soup.findAll('table', attrs={'class':'contentt'}):
            subject_tag = item.find('td', attrs={'class':'subject'}).next
            subject = ''.join(subject_tag.findAll(text=True))
            complete = item.find('td', attrs={'class':'complete'}).string
            nzb_url = 'http://newzleech.com' + item.find('td', attrs={'class':'get'}).next.get('href')
            
            if subject == entry['title']:
                if complete != u'100':
                    log.debug('Found incomplete %s from newzleech, skipping ..' % entry['title'])
                    continue
                log.info('Found \'%s\' from newzleech' % entry['title'])
                entry['url'] = nzb_url
