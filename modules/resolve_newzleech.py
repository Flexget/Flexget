import urllib, urllib2
import logging
import re
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

        url = u'http://newzleech.com/?' + urllib.urlencode({'q':entry['title'].encode('latin1'), 'm':'search', 'group':'', 'min':'min', 'max':'max', 'age':'', 'minage':'', 'adv':''})
        log.debug('Search url: %s' % url)
        
        txheaders = {
            'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
            'Keep-Alive': '300',
            'Connection': 'keep-alive',
        }
        
        req = urllib2.Request(url, None, txheaders)
        try:
            page = urllib2.urlopen(req)
        except IOError, e:
            if hasattr(e, 'reason'):
                raise ModuleWarning('Failed to reach server. Reason: %s' % e.reason)
            elif hasattr(e, 'code'):
                raise ModuleWarning('The server couldn\'t fulfill the request. Error code: %s' % e.code)

        soup = BeautifulSoup(page)
        
        for item in soup.findAll('table', attrs={'class':'contentt'}):
            subject_tag = item.find('td', attrs={'class':'subject'}).next
            subject = ''.join(subject_tag.findAll(text=True))
            complete = item.find('td', attrs={'class':'complete'}).string
            nzb_url = 'http://newzleech.com' + item.find('td', attrs={'class':'get'}).next.get('href')
            
            # generate regexp from entry title and see if it matches subject
            regexp = entry['title']
            wildcardize = [' ', '-'] # dot needs to be last or replace screws it up
            for wild in wildcardize:
                regexp = regexp.replace(wild, '.')
            regexp = '.*' + regexp + '.*'
            log.debug('Title regexp: %s' % regexp)
            
            if re.match(regexp, subject):
                log.debug('%s matches to regexp' % subject)
                if complete != u'100':
                    log.debug('Match is incomplete %s from newzleech, skipping ..' % entry['title'])
                    continue
                log.info('Found \'%s\'' % entry['title'])
                entry['url'] = nzb_url
                break
        else:
            log.debug('Unable to find %s' % entry['title'])