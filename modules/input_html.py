import urllib
import urllib2
import urlparse
import logging
import re

log = logging.getLogger('html')

# this way we don't force users to install bs incase they do not want to use module http
soup_present = True
soup_err = "Module feed_html requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository."

try:
    from BeautifulSoup import BeautifulSoup
except:
    log.warning(soup_err)
    soup_present = False

class InputHtml:
    """
        Parses urls from html page. Usefull on sites which have direct download
        links of any type (mp3, jpg, torrent, ...).
        
        Many anime-fansubbers do not provide RSS-feed, this works well in many cases.
        
        Configuration expects url parameter.

        Note: This returns ALL links on url so you need to configure patterns filter
        to match only to desired content.
    """

    def register(self, manager, parser):
        manager.register(instance=self, event="input", keyword="html", callback=self.run)

    def run(self, feed):
        if not soup_present: raise Exception(soup_err)
        pageurl = feed.get_input_url('html')

        log.debug("InputModule html requesting url %s" % pageurl)

        try:
            page = urllib2.urlopen(pageurl)
            soup = BeautifulSoup(page)
        except timeout:
            log.warning("Timed out opening page")
            return
        except urllib2.URLError, e:
            log.warning("URLError when opening page")
            return
        
        for link in soup.findAll('a'):
            if not link.has_key("href"): continue
            title = link.string
            if title == None: continue
            url = link['href']
            title = str(title).strip()
            if not title: continue

            # fix broken urls
            if url.startswith('//'):
                url = "http:" + url
            elif not url.startswith('http://') or not url.startswith('https://'):
                url = urlparse.urljoin(pageurl, url)
                
            #url_readable = urllib.unquote(url)

            # in case the title contains xxxxxxx.torrent - foooo.torrent clean it a bit (get upto first .torrent)
            if title.lower().find('.torrent') > 0:
                title = title[:title.lower().find(".torrent")]

            entry = {}
            entry['url'] = url.encode() # removes troublesome unicode
            entry['title'] = title

            feed.entries.append(entry)

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)

    from test_tools import MockFeed
    feed = MockFeed()
    feed.config['html'] = sys.argv[1]

    module = InputHtml()
    module.run(feed)

    feed.dump_entries()
