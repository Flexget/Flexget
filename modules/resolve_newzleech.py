import urllib, urllib2
import logging
from manager import ModuleWarning

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger("newzleech")

class ResolveNewzleech:
    """
        Resolver or search by using newzleech.com
        TODO: implement resolving
    """

    def register(self, manager, parser):
        manager.register('newzleech', group='search')

    # Search API
    def search(self, feed, entry):
        try:
            from BeautifulSoup import BeautifulSoup
        except:
            raise ModuleWarning('Newzleech requires BeautifulSoup')

        url = u'http://newzleech.com/?' + urllib.urlencode({'q':entry['title'].encode('latin1'), 'group':'', 'min':'', 'max':'', 'age':'', 'minage':''})
        log.debug('Search url: %s' % url)
        
        # need to fake user agent and refferer
        txheaders =  {'User-agent' : 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)', 'Referer' : 'http://newzleech.com/'}
        req = urllib2.Request(url, None, txheaders)
        try:
            page = urllib2.urlopen(req)
        except IOError, e:
            if hasattr(e, 'reason'):
                raise ModuleWarning('Failed to reach server. Reason: %s' % e.reason)
            elif hasattr(e, 'code'):
                raise ModuleWarning('The server couldn\'t fulfill the request. Error code: %s' % e.code)

        soup = BeautifulSoup(page)
        
        print soup
        
        for item in soup.findAll('table', attrs={'class':'contentt'}):
            print item
            subject_tag = item.find('td', attrs={'class':'subject'}).next
            subject = ''.join(subject_tag.findAll(text=True))
            complete = item.find('td', attrs={'class':'complete'}).string
            nzb_url = 'http://newzleech.com' + item.find('td', attrs={'class':'get'}).next.get('href')
            
            log.debug('subject: %s' % subject)
            if subject == entry['title']:
                if complete != u'100':
                    log.debug('Found incomplete %s from newzleech, skipping ..' % entry['title'])
                    continue
                log.info('Found \'%s\' from newzleech' % entry['title'])
                entry['url'] = nzb_url
                break
