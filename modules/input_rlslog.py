import urllib
import urllib2
import urlparse
import logging
import re
import yaml
from httplib import BadStatusLine

log = logging.getLogger('rlslog')

# this way we don't force users to install bs incase they do not want to use module http
soup_present = True
soup_err = "Module rlslog requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository."

try:
    from BeautifulSoup import BeautifulSoup
except:
    log.warning(soup_err)
    soup_present = False

class RlsLog:

    """
        Adds support for rlslog.net as a feed.

        In case of movies the module supplies pre-parses IMDB-details (helps when chaining with filter_imdb).
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

    def parse_rlslog(self, rlslog_url, feed):
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

                # test if entry with this url would be resolvable (downloadable)
                temp = {}
                temp['title'] = release['title']
                temp['url'] = link_href
                if feed.resolvable(temp):
                    release['url'] = link_href

            # reject if no torrent link
            if release.has_key('url'):
                releases.append(release)
            else:
                log.info('%s rejected due to missing or unrecognized torrent link' % (release['title']))

        return releases

    def run(self, feed):
        if not soup_present: raise Exception(soup_err)

        try:
	    releases = self.parse_rlslog(feed.get_input_url('rlslog'), feed)
        except urllib2.HTTPError, e:
            raise Warning('RlsLog was unable to complete task. HTTPError %s' % (e.code))
        except urllib2.URLError, e:
            raise Warning('RlsLog was unable to complete task. URLError %s' % (e.reason))
        except BadStatusLine:
            raise Warning('RlsLog was unable to complete task. Got BadStatusLine.')

        for release in releases:
            # construct entry from release
            entry = {}

            def apply_field(d_from, d_to, f):
                if d_from.has_key(f):
                    if d_from[f] == None: return # None values are not wanted!
                    d_to[f] = d_from[f]

            for field in ['title', 'url', 'imdb_url', 'imdb_score', 'imdb_votes']:
                apply_field(release, entry, field)

            feed.entries.append(entry)

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)

    r = RlsLog()
    from test_tools import MockFeed
    feed = MockFeed()
    feed.config['rlslog'] = sys.argv[1]

    r.run(feed)
    print yaml.dump(feed.entries)
