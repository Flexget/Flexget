import urllib
import urllib2
import urlparse
import logging
import re
import yaml

log = logging.getLogger('rlslog')

# this way we don't force users to install bs incase they do not want to use module http
soup_present = True
soup_err = "Module rlslog requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository."

try:
    from BeautifulSoup import BeautifulSoup
except:
    log.warning(soup_err)
    soup_present = False

class NewTorrents:
    """NewTorrents parsing utilities"""

    def __init__(self, raw_url, title):
        self.raw_url = raw_url
        self.title = title

    def request_torrent_url(self):
        """Returns torrent from either search url or download page"""
        if (self.raw_url.startswith("http://www.newtorrents.info/?q=") or self.raw_url.startswith("http://www.newtorrents.info/search")) and (self.title != None):
            #log.debug("NewTorrents get_torrent_url using search")
            return self.__get_torrent_url_from_search(self.raw_url, self.title)
        else:
            #log.debug("NewTorrents get_torrent_url using page")
            return self.__get_torrent_url_from_page(self.raw_url)

    # TODO: refactor parameters to use self
    
    def __get_torrent_url_from_page(self, url):
        """Parses torrent url from newtorrents download page"""
        page = urllib2.urlopen(url)
        data = page.read()
        p = re.compile("copy\(\'(.*)\'\)", re.IGNORECASE)
        f = p.search(data)
        if f==None:
            log.debug("NewTorrents get_torrent_url_from_page failed")
            return None
        else:
            return f.groups()[0]

    def __get_torrent_url_from_search(self, url, name):
        """Parses torrent download url (requires release name) from search results"""
        name = name.replace('.',' ').lower()
        page = urllib2.urlopen(url)
        soup = BeautifulSoup(page)
        torrents = []
        for link in soup.findAll('a', attrs={'href': re.compile('down.php')}):
            torrent_url = "http://www.newtorrents.info%s" % link.get('href')
            release_name = link.parent.next.get('title').replace('.',' ').lower()
            if release_name == name:
                torrents.append(torrent_url)
            else:
                log.debug("NewTorrents rejecting search result: '%s' != '%s'" % (release_name, name))

        # choose the torrent
        if not torrents:
            log.debug("NewTorrents did not found any matches in search result")
            return None
        else:
            if len(torrents) == 1:
                log.debug("NewTorrents found only one matching search result.")
            else:
                log.debug('NewTorrents search results contains multiple matches, using first occurence from: %s' % torrents)
                # TODO: use the one that has most downloaders / seeders
            return torrents[0]

class PirateBay:
    """Piratebay parsing utilities"""

    def __init__(self, raw_url, title):
        self.raw_url = raw_url
        self.title = title

    def request_torrent_url(self):
        page = urllib2.urlopen(self.raw_url)
        soup = BeautifulSoup(page)
        tag_div = soup.find("div", attrs={"class":"download"})
        tag_a = tag_div.find("a")
        torrent_url = tag_a.get('href')
        return torrent_url

class RlsLog:

    """
        Adds support for rlslog.net as a feed.
        
        If rlslog entry has NewTorrents download link then torrent url is parsed from there.
        If rlslog entry has NewTorrents search link, we try to look from there if any of the results match entry title.
        On multiple NewTorrents-links per entry have unknown effects ...

        Module caches all successfull NewTorrents 'download torrent'-parses, hence module makes only one request per
        rlslog-entry to NewTorrents thus eliminating any potential DDOS effect and or bandwith wasting.

        NEW: Supports also piratebay links

        In case of movies the module supplies pre-parse IMDB-details (helps when chaining with filter_imdb).
    """

    def register(self, manager, parser):
        manager.register(instance=self, event="input", keyword="rlslog", callback=self.run)

    def parse_imdb(self, s):
        score = None
        votes = None
        re_votes = re.compile("\((\d*).votes\)", re.IGNORECASE)
        re_score = [re.compile("(\d\.\d)"), re.compile("(\d)\/10")]
        for r in re_score:
            f = r.search(s)
            if f != None:
                score = float(f.groups()[0])
                break
        f = re_votes.search(s.replace(",",""))
        if f != None:
            votes = f.groups()[0]
        log.debug("parse_imdb returning score: '%s' votes: '%s' from: '%s'" % (str(score), str(votes), s))
        return (score, votes)

    def parse_rlslog(self, rlslog_url):
        """Parse configured url and return releases array"""
        if not soup_present:
            log.error(soup_err)
            return
        page = urllib2.urlopen(rlslog_url)
        soup = BeautifulSoup(page)
        releases = []
        for entry in soup.findAll('div', attrs={"class" : "entry"}):
            release = {}
            h3 = entry.find('h3', attrs={"class" : "entrytitle"})
            if not h3:
                log.debug('No h3 entrytitle')
                continue
            release['title'] = h3.a.string.strip()
            entrybody = entry.find('div', attrs={"class" : "entrybody"})
            if not entrybody:
                log.debug("No entrybody")
                continue

            log.debug("Processing title %s" % (release['title']))

            rating = entrybody.find('strong', text=re.compile('imdb rating\:', re.IGNORECASE))
            if rating != None:
                score_raw = rating.next.string
                if score_raw != None:
                    release['imdb_score'], release['imdb_votes'] = self.parse_imdb(score_raw)
            
            for link in entrybody.findAll('a'):
                link_name = link.string
                if link_name == None:
                    continue
                link_name = link_name.strip().lower()
                link_href = link['href']
                # handle imdb link
                if link_name == "imdb":
                    release['imdb_url'] = link_href
                    score_raw = link.next.next.string
                    if not release.has_key('imdb_score') and not release.has_key('imdb_votes') and score_raw != None:
                        release['imdb_score'], release['imdb_votes'] = self.parse_imdb(score_raw)
                # handle newtorrents link
                if link_href.startswith('http://www.newtorrents.info'):
                    release['site'] = NewTorrents(link_href, release['title'])
                # handle piratebay link
                if link_href.startswith('http://thepiratebay.org'):
                    release['site'] = PirateBay(link_href, release['title'])

            # reject if no torrent link
            if release.has_key('site'):
                releases.append(release)
            else:
                log.info('%s rejected due missing torrents-link' % (release['title']))

        return releases

    def run(self, feed):
        if not soup_present: raise Exception(soup_err)

        try:
	    releases = self.parse_rlslog(feed.get_input_url('rlslog'))
        except urllib2.URLError, e:
            raise Warning('RlsLog was unable to complete task. URLError %s' % (e.reason))

        for release in releases:
            # try to lookup torrent url (by site url) from cache
            torrent_url = feed.cache.get(release['site'].raw_url, None)
            if feed.manager.options.nocache: torrent_url = None
            if torrent_url == None:
                # find out actual torrent link from site (requests page and parses it)
                try:
                    torrent_url = release['site'].request_torrent_url()
                except urllib2.URLError, e:
                    log.error('Unable to get torrent url for release %s. URLError %s' % (release['title'], e.reason))
                    continue
            if torrent_url != None:
                # add torrent url to cache for future usage
                feed.cache.store(release['site'].raw_url, torrent_url, 30)

                # construct entry from our release
                entry = {}
                entry['url'] = torrent_url
                def apply_field(d_from, d_to, f):
                    if d_from.has_key(f):
                        if d_from[f] == None: return # None values are not wanted!
                        d_to[f] = d_from[f]
                for field in ['title', 'imdb_url', 'imdb_score', 'imdb_votes']:
                    apply_field(release, entry, field)
                feed.entries.append(entry)
            else:
                log.debug("Unable to get torrent url for '%s'" % (release['title']))



if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)

    """
    n = NewTorrents()
    p2 = None
    if len(sys.argv) > 2:
        p2 = sys.argv[2]
    else:
        p2 = None
    url = n.get_torrent_url(sys.argv[1], p2)
    print yaml.dump(url)
    """

    r = RlsLog()
    from test_tools import MockFeed
    feed = MockFeed()

    r.run(feed)
    print yaml.dump(feed.entries)
