import urllib2
import urlparse
import logging
from socket import timeout
from feed import Entry
from manager import ModuleWarning

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('html')

# this way we don't force users to install bs incase they do not want to use module http
soup_present = True
soup_err = 'Module feed_html requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository.'

try:
    from BeautifulSoup import BeautifulSoup
except:
    soup_present = False

class InputHtml:
    """
        Parses urls from html page. Usefull on sites which have direct download
        links of any type (mp3, jpg, torrent, ...).
        
        Many anime-fansubbers do not provide RSS-feed, this works well in many cases.
        
        Configuration expects url parameter.

        Note: This returns ALL links on url so you need to configure filters
        to match only to desired content.
    """

    def register(self, manager, parser):
        manager.register('html')
        
    def validate(self, config):
        """Validate given configuration"""
        from validator import DictValidator
        if isinstance(config, dict):
            root = DictValidator()
            root.accept('url', str, required=True)
            root.accept('title_from_url', bool)
            root.accept('dump', str)
            root.validate(config)
            return root.errors.messages
        elif isinstance(config, str):
            return []
        else:
            return ['wrong datatype']

    def feed_input(self, feed):
        if not soup_present: raise Exception(soup_err)
        config = feed.config['html']
        if not isinstance(config, dict):
            config = {}
        pageurl = feed.get_input_url('html')

        log.debug('InputModule html requesting url %s' % pageurl)

        try:
            page = urllib2.urlopen(pageurl)
            soup = BeautifulSoup(page)
            log.debug('Detected encoding %s' % soup.originalEncoding)
        except IOError, e:
            if hasattr(e, 'reason'):
                raise ModuleWarning('Failed to reach server. Reason: %s' % e.reason, log)
            elif hasattr(e, 'code'):
                raise ModuleWarning('The server couldn\'t fulfill the request. Error code: %s' % e.code, log)
        
        # dump received content into a file
        if config.has_key('dump'):
            name = config['dump']
            log.info('Dumping %s into %s' % (pageurl, name))
            data = soup.prettify()
            f = open(name, 'w')
            f.write(data)
            f.close()
        
        for link in soup.findAll('a'):
            if not link.has_key('href'): continue
            title = link.string
            if title == None: continue
            title = title.replace(u'\u200B', u'').strip()
            if not title: continue
            url = link['href']

            # fix broken urls
            if url.startswith('//'):
                url = 'http:' + url
            elif not url.startswith('http://') or not url.startswith('https://'):
                url = urlparse.urljoin(pageurl, url)
            
            if config.get('title_from_url', False):
                import urllib
                parts = urllib.splitquery(url[url.rfind('/')+1:])
                title = urllib.unquote_plus(parts[0])
                log.debug('title_from_url: %s' % title)
            else:
                # TODO: there should be this kind of function in feed, trunk unit test has it already
                # move it to feed?
                def exists(title):
                    for entry in feed.entries:
                        if entry['title'] == title:
                            return True
                    return False
            
                # title link should be unique, add count to end if it's not
                i = 0
                orig_title = title
                while True:
                    if not exists(title):
                        break
                    i += 1
                    title = '%s (%s)' % (orig_title, i)

            # in case the title contains xxxxxxx.torrent - foooo.torrent clean it a bit (get upto first .torrent)
            # TODO: hack
            if title.lower().find('.torrent') > 0:
                title = title[:title.lower().find('.torrent')]

            entry = Entry()
            entry['url'] = url
            entry['title'] = title

            feed.entries.append(entry)