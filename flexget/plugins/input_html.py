import urllib2
import urlparse
import logging
from socket import timeout
from flexget.feed import Entry
from flexget.plugin import *
import re
from flexget.utils.soup import get_soup

log = logging.getLogger('html')

class InputHtml:
    """
        Parses urls from html page. Usefull on sites which have direct download
        links of any type (mp3, jpg, torrent, ...).
        
        Many anime-fansubbers do not provide RSS-feed, this works well in many cases.
        
        Configuration expects url parameter.

        Note: This returns ALL links on url so you need to configure filters
        to match only to desired content.
    """
    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        advanced = root.accept('dict')
        advanced.accept('url', key='url', required=True)
        advanced.accept('text', key='dump')
        advanced.accept('boolean', key='title_from_url')
        advanced.accept('boolean', key='title_from_title')
        return root

    def feed_input(self, feed):
        config = feed.config['html']
        if not isinstance(config, dict):
            config = {}
        pageurl = feed.get_input_url('html')

        log.debug('InputPlugin html requesting url %s' % pageurl)

        try:
            page = urllib2.urlopen(pageurl)
            soup = get_soup(page)
            log.debug('Detected encoding %s' % soup.originalEncoding)
        except IOError, e:
            if hasattr(e, 'reason'):
                raise PluginError('Failed to reach server. Reason: %s' % e.reason, log)
            elif hasattr(e, 'code'):
                raise PluginError('The server couldn\'t fulfill the request. Error code: %s' % e.code, log)
        
        # dump received content into a file
        if 'dump' in config:
            name = config['dump']
            log.info('Dumping %s into %s' % (pageurl, name))
            data = soup.prettify()
            f = open(name, 'w')
            f.write(data)
            f.close()
        
        for link in soup.findAll('a'):
            if not link.has_key('href'):
                continue
            title = link.contents[0]

            if title == None: 
                title = link.next.string
                if title == None:
                    continue

            title = title.replace(u'\u200B', u'').strip()
            if not title: 
                continue
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
            elif config.get('title_from_title', False) and link.has_key('title'):
                title = link['title']
                log.debug('title_from_title: %s' % title)
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

register_plugin(InputHtml, 'html')
