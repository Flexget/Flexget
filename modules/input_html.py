__instance__ = "InputHtml"

import urllib
import urllib2
import urlparse
import logging
import re

# this way we don't force users to install bs incase they do not want to use module http
soup_present = True
soup_err = "Module feed_html requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository."

try:
    from BeautifulSoup import BeautifulSoup
except:
    logging.warning(soup_err)
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

    def register(self, manager):
        manager.register(instance=self, type="input", keyword="html", callback=self.run)

    def get_filename(self, href):
        return href[href.rfind("/")+1:]

    def run(self, feed):
        if not soup_present: raise Exception(soup_err)

        pageurl = feed.get_input_url('html')

        logging.debug("InputModule html requesting url %s" % pageurl)

        page = urllib2.urlopen(pageurl)
        soup = BeautifulSoup(page)
        for link in soup.findAll('a'):
            if not link.has_key("href"): continue
            title = link.contents[0]
            url = link['href']

            # fix broken urls
            if url.startswith('//'):
                url = "http:" + url
            elif url.startswith('/'):
                url = urlparse.urljoin(pageurl, url)
                
            url_readable = urllib.unquote(url)

            #full_title = "%s - %s" % (self.get_filename(url_readable), title)
            full_title = str(title)
            # incase title contains xxxxxxx.torrent - foooo.torrent clean it a bit (get upto first .torrent)
            if (full_title.lower().find('.torrent')):
                full_title = full_title[:full_title.lower().find(".torrent")]

            entry = {}
            entry['url'] = url.encode() # removes troublesome unicode
            entry['title'] = full_title

            feed.entries.append(entry)
