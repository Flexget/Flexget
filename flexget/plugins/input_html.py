import urllib2
import urlparse
import logging
import BeautifulSoup
from flexget.feed import Entry
from flexget.plugin import *
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
        advanced.accept('text', key='title_from')
        return root

    @internet(log)
    def on_feed_input(self, feed):
        config = feed.config['html']
        if not isinstance(config, dict):
            config = {}
        pageurl = feed.get_input_url('html')

        log.debug('InputPlugin html requesting url %s' % pageurl)

        page = urllib2.urlopen(pageurl)
        soup = get_soup(page)
        log.debug('Detected encoding %s' % soup.originalEncoding)
        
        # dump received content into a file
        if 'dump' in config:
            name = config['dump']
            log.info('Dumping %s into %s' % (pageurl, name))
            data = soup.prettify()
            f = open(name, 'w')
            f.write(data)
            f.close()
            
        self.create_entries(feed, pageurl, soup, config)

    def create_entries(self, feed, pageurl, soup, config):

        entries = []

        def title_exists(title):
            """Helper method. Return True if title is already added to entries"""
            for entry in entries:
                if entry['title'] == title:
                    return True
        
        for link in soup.findAll('a'):
            # not a valid link
            if not link.has_key('href'):
                continue
            # no content in link
            if not link.contents:
                continue
            
            title = link.contents[0]
            
            # tag inside link
            if isinstance(title, BeautifulSoup.Tag):
                log.debug('title is tag: %s' % title)
                continue

            # just unable to get any decent title
            if title is None: 
                title = link.next.string
                if title is None:
                    continue

            # stip unicode whitespaces
            title = title.replace(u'\u200B', u'').strip()
            
            if not title: 
                continue
            
            url = link['href']

            # fix broken urls
            if url.startswith('//'):
                url = 'http:' + url
            elif not url.startswith('http://') or not url.startswith('https://'):
                url = urlparse.urljoin(pageurl, url)

            title_from = config.get('title_from', 'auto')
            if title_from == 'url':
                import urllib
                parts = urllib.splitquery(url[url.rfind('/')+1:])
                title = urllib.unquote_plus(parts[0])
                log.debug('title from url: %s' % title)
            elif title_from == 'title' and link.has_key('title'):
                title = link['title']
                log.debug('title from title: %s' % title)
            else:
                # automatic mode, check if title is unique
                if title_exists(title):
                    log.info('Link names seem to be useless, auto-enabling \'title_from: url\'')
                    config['title_from'] = 'url'
                    # start from the beginning  ...
                    self.create_entries(feed, pageurl, soup, config)
                    return

            if title_exists(title):
                # title link should be unique, add CRC32 to end if it's not
                import zlib
                hash = zlib.crc32(url)
                crc32 = '%08X' % (hash & 0xFFFFFFFF)
                title = '%s [%s]' % (title, crc32)
                # truly duplicate, title + url crc already exists in queue
                if title_exists(title):
                    continue
                log.debug('uniqued title to %s' % title)

            # in case the title contains xxxxxxx.torrent - foooo.torrent clean it a bit (get upto first .torrent)
            # TODO: hack
            if title.lower().find('.torrent') > 0:
                title = title[:title.lower().find('.torrent')]

            entry = Entry()
            entry['url'] = url
            entry['title'] = title

            entries.append(entry)

        # add from queue to feed
        feed.entries.extend(entries)


register_plugin(InputHtml, 'html')
