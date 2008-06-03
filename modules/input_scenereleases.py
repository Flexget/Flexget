import urllib2
import logging
import re
from httplib import BadStatusLine
from feed import Entry

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('scenereleases')

# this way we don't force users to install bs incase they do not want to use module http
soup_present = True
soup_err = 'Module rlslog requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository.'

try:
    from BeautifulSoup import BeautifulSoup
except:
    soup_present = False

class InputScenereleases:

    """
        Uses scenereleases.info category as input.

        Example:

        scenereleases: http://www.scenereleases.info/search/label/Movies%20-%20DVD%20Rip
    """

    def register(self, manager, parser):
        manager.register(event='input', keyword='scenereleases', callback=self.run)

    def parse_imdb(self, s):
        score = None
        votes = None
        re_votes = re.compile('\((\d*).votes\)', re.IGNORECASE)
        re_score = [re.compile('(\d\.\d)'), re.compile('(\d)\/10')]
        for r in re_score:
            f = r.search(s)
            if f != None:
                score = float(f.group(1))
                break
        f = re_votes.search(s.replace(',',''))
        if f != None:
            votes = f.group(1)
        log.debug("parse_imdb returning score: '%s' votes: '%s' from: '%s'" % (str(score), str(votes), s))
        return (score, votes)

    def parse_site(self, url, feed):
        """Parse configured url and return releases array"""
        
        page = urllib2.urlopen(url)
        soup = BeautifulSoup(page)
            
        releases = []
        for entry in soup.findAll('div', attrs={'class':re.compile('post uncustomized-post-template', re.IGNORECASE)}):
            release = {}
            title = entry.find('h2')
            if not title:
                log.debug('No h2 entrytitle')
                continue
            release['title'] = title.a.string.strip()

            log.debug('Processing title %s' % (release['title']))

            """
            # TODO: parse imdb values
            rating = entry.find('strong', text=re.compile('imdb rating\:', re.IGNORECASE))
            if rating != None:
                score_raw = rating.next.string
                if score_raw != None:
                    release['imdb_score'], release['imdb_votes'] = self.parse_imdb(score_raw)
            """
            
            for link in entry.findAll('a'):
                link_name = link.string
                if link_name == None:
                    continue
                link_name = link_name.strip().lower()
                link_href = link['href']
                #log.debug('found link %s -> %s' % (link_name, link_href))
                # handle imdb link
                if link_name.lower() == 'imdb':
                    log.debug('found imdb link %s' % link_href)
                    release['imdb_url'] = link_href
                    """
                    score_raw = link.next.next.string
                    if not release.has_key('imdb_score') and not release.has_key('imdb_votes') and score_raw != None:
                        release['imdb_score'], release['imdb_votes'] = self.parse_imdb(score_raw)
                    """

                # test if entry with this url would be resolvable (downloadable)
                temp = {}
                temp['title'] = release['title']
                temp['url'] = link_href
                if feed.resolvable(temp):
                    release['url'] = link_href

                # if name is torrent
                if link_name.lower() == 'torrent':
                    log.debug('found torrent url %s' % link_href)
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
	    releases = self.parse_site(feed.get_input_url('scenereleases'), feed)
        except urllib2.HTTPError, e:
            raise Warning('scenereleases was unable to complete task. HTTPError %s' % (e.code))
        except urllib2.URLError, e:
            raise Warning('scenereleases was unable to complete task. URLError %s' % (e.reason))
        except BadStatusLine:
            raise Warning('scenereleases was unable to complete task. Got BadStatusLine.')

        for release in releases:
            # construct entry from release
            entry = Entry()
            def apply_field(d_from, d_to, f):
                if d_from.has_key(f):
                    if d_from[f] == None: return # None values are not wanted!
                    d_to[f] = d_from[f]

            for field in ['title', 'url', 'imdb_url', 'imdb_score', 'imdb_votes']:
                apply_field(release, entry, field)

            feed.entries.append(entry)
