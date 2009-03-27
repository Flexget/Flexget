import urllib2
import urlparse
import logging
from socket import timeout
from feed import Entry
from manager import ModuleWarning
from BeautifulSoup import BeautifulSoup

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('tvtorrents')

class InputTVTorrents:
    """
        A customized HTML input module. Parses out full torrent URLs from 
        TVTorrents' page for Recently Aired TV shows.

        A bit fragile right now, because it depends heavily on the exact 
        structure of the HTML.

        Just set tvt: true in your config, and provide the path to your login 
        cookie by using the cookies module.
        
        Note: Of yourse, you need to configure patterns filter to match only 
        desired content. The series filter does NOT appear to work well with
        this module yet - just use a pattern like (lost|csi).*?720p until we
        figure out why.

        Module-specific code by Fredrik Braenstroem.
    """

    def register(self, manager, parser):
        manager.register('tvt')

    def validate(self, config):
        # TODO: validate that parameter is url ...
        return []

    def feed_input(self, feed):
        pageurl = "http://tvtorrents.com/loggedin/recently_aired.do"
        log.debug("InputModule tvtorrents requesting url %s" % pageurl)

        try:
            page = urllib2.urlopen(pageurl)
            soup = BeautifulSoup(page)
        except timeout:
            raise ModuleWarning("Timed out opening page", log)
        except urllib2.URLError:
            raise ModuleWarning("URLError when opening page", log)
        
        hscript = soup.find('script', src=None).string
        hlines = hscript.splitlines()
        hash = hlines[15].strip().split("'")[1]
#        log.info("InputModule tvtorrents found hash: %s" % hash)
        digest = hlines[16].strip().split("'")[1]
#        log.info("InputModule tvtorrents found digest: %s" % digest)
        hurl = hlines[17].strip().split("'")
        hashurl = hurl[1] + "%s" + hurl[3] + digest + hurl[5] + hash
#        log.info("InputModule tvtorrents constructed base URL: %s" % hashurl)

        for link in soup.findAll('a'):
            if not link.has_key("href"): continue
            url = link['href']
            title = link.string

#            if url == "#" and link.has_key('onclick') and link['onclick'].find("loadTorrent") != -1:
            if link.has_key('onclick') and link['onclick'].find("loadTorrent") != -1:
                infohash = link['onclick'].split("'")[1]
#                log.info("*** TvT: info_hash: %s" % infohash)
#                sname = link.parent.parent.previous.previous.parent.contents[1].a.string # For old-style page

                td = link.parent.parent.contents[4]
#                log.info("TvT: element: %s" % td.string)

                sname = td.contents[0].strip()
#                log.info("TvT: show name: %s" % sname.string)

                epi = td.contents[2].contents[0].strip()
#                log.info("TvT: episode: %s" % epi.string)

#                epnr = link.parent.previous.previous
#                eptitle = link.previous.previous
#                title = "%s - %s - %s" % (sname, epnr, eptitle)
                title = "%s - %s" % (sname, epi)
                url = hashurl % (infohash,)
#                log.info("TvT: found episode: %s (%s)" % (title, url))
#                continue
            else:
                continue
            if title == None: continue

            title = title.strip()
            if not title: continue

            # fix broken urls
            if url.startswith('//'):
                url = "http:" + url
            elif not url.startswith('http://') or not url.startswith('https://'):
                url = urlparse.urljoin(pageurl, url)
                
            # in case the title contains xxxxxxx.torrent - foooo.torrent clean it a bit (get upto first .torrent)
            if title.lower().find('.torrent') > 0:
                title = title[:title.lower().find(".torrent")]

            entry = Entry()
            entry['url'] = url
            entry['title'] = title

            feed.entries.append(entry)
