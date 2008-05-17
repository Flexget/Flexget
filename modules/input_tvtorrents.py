import urllib
import urllib2
import urlparse
import logging
from socket import timeout
import re
from feed import Entry

log = logging.getLogger('tvtorrents')

# this way we don't force users to install bs incase they do not want to use module http
soup_present = True
soup_err = "Module tvtorrents requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository."

try:
    from BeautifulSoup import BeautifulSoup
except:
    log.warning(soup_err)
    soup_present = False

class InputTVTorrents:
    """
        A customized HTML input module. Parses out full torrent URLs from 
        TVTorrents' page for Recently Aired TV shows.

        A bit fragile right now, because it depends heavily on the exact 
        structure of the HTML, as it looked today - 2008-05-17.

        Just set tvt: true in your config, and provide the path to your login 
        cookie by using the [[cookies]] module.
        
        Note: Of yourse, you need to configure [[patterns]] filter to match only 
        desired content. The [[series]] filter does NOT appear to work well with
        this module yet - just use a pattern like (lost|csi).*?720p until we
        figure out why.

        Module-specific code by Fredrik Br&auml;enstr&ouml;m.
    """

    def register(self, manager, parser):
        manager.register(instance=self, event="input", keyword="tvt", callback=self.run)

    def run(self, feed):
        if not soup_present: raise Exception(soup_err)
#        if feed.name.lower().find("tvtorrents") == -1: skipthismodule
        # Um... not possible to discern feed type based on name... yet... (If implemented it should be in manager.py anyways.) *I'm sleepy*
        pageurl = "http://tvtorrents.com/loggedin/recently_aired.do" # feed.get_input_url('html')

        log.debug("InputModule tvtorrents requesting url %s" % pageurl)

        try:
            page = urllib2.urlopen(pageurl)
            soup = BeautifulSoup(page)
        except timeout:
            log.warning("Timed out opening page")
            return
        except urllib2.URLError, e:
            log.warning("URLError when opening page")
            return
        
#        if pageurl.find("tvtorrents") != -1:
#            tvtorrents = 1
#            hline = soup.find(text=re.compile(".*?torrent\.tvtorrents\.com.*?"))
        hscript = soup.find('script', src=None).string
        hlines = hscript.splitlines()
        hash = hlines[15].strip().split("'")[1]
        digest = hlines[16].strip().split("'")[1]
        hurl = hlines[17].strip().split("'")
        hashurl = hurl[1] + "%s" + hurl[3] + digest + hurl[5] + hash

        for link in soup.findAll('a'):
            if not link.has_key("href"): continue
            url = link['href']
            title = link.string

#            if tvtorrents:
            if url == "#" and link.has_key('onclick') and link['onclick'].find("loadTorrent") != -1:
#                if url == "#" and link.has_key('onclick') and (title == None or title == "download"):
                infohash = link['onclick'].split("'")[1]
                sname = link.parent.parent.previous.previous.parent.contents[1].a.string
                epnr = link.parent.previous.previous
                eptitle = link.previous.previous
                title = "%s - %s - %s" % (sname, epnr, eptitle)
                url = hashurl % (infohash,)
#                    print "%s: %s" % (infohash, ntitle)
#                    print "%s: %s" % (title, url)
            else:
                continue
                

            if title == None: continue

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

            entry = Entry()
            entry['url'] = url
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
