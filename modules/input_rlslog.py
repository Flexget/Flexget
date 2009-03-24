import urllib2
import logging
import re
from httplib import BadStatusLine
from feed import Entry
from manager import ModuleWarning

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('rlslog')

# this way we don't force users to install bs incase they do not want to use module http
soup_present = True
soup_err = 'Module rlslog requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository.'

try:
    from BeautifulSoup import BeautifulSoup
except:
    soup_present = False

class RlsLog:

    """
        Adds support for rlslog.net as a feed.

        In case of movies the module supplies pre-parses IMDB-details
        (helps when chaining with filter_imdb).
    """

    def register(self, manager, parser):
        manager.register('rlslog')

    def validator(self):
        import validator
        return validator.factory('url')

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
            votes = int(f.group(1))
        log.debug("parse_imdb returning score: '%s' votes: '%s' from: '%s'" % (str(score), str(votes), s))
        return (score, votes)

    def parse_rlslog(self, rlslog_url, feed):
        """Parse configured url and return releases array"""
        
        page = urllib2.urlopen(rlslog_url)
        soup = BeautifulSoup(page)
            
        releases = []
        for entry in soup.findAll('div', attrs={'class' : 'entry'}):
            release = {}
            h3 = entry.find('h3', attrs={'class' : 'entrytitle'})
            if not h3:
                log.debug('FAIL: No h3 entrytitle')
                continue
            release['title'] = h3.a.string.strip()
            entrybody = entry.find('div', attrs={'class' : 'entrybody'})
            if not entrybody:
                log.debug('FAIL: No entrybody')
                continue

            log.debug('Processing title %s' % (release['title']))

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
                # parse imdb link
                if link_name == 'imdb':
                    release['imdb_url'] = link_href
                    score_raw = link.next.next.string
                    if not 'imdb_score' in release and not 'imdb_votes' in release and score_raw != None:
                        release['imdb_score'], release['imdb_votes'] = self.parse_imdb(score_raw)

                # test if entry with this url would be resolvable (downloadable)
                temp = {}
                temp['title'] = release['title']
                temp['url'] = link_href
                resolver = feed.manager.get_module_by_name('resolver')
                if resolver['instance'].resolvable(feed, temp):
                    release['url'] = link_href
                    log.debug('--> accepting %s (resolvable)' % link_href)
                else:
                    log.debug('<-- ignoring %s (non-resolvable)' % link_href)

            # reject if no torrent link
            if not 'url' in release:
                feed.log_once('%s skipped due to missing or unrecognized download link' % (release['title']), log)
            else:
                releases.append(release)

        return releases

    def feed_input(self, feed):
        if not soup_present: raise Exception(soup_err)

        try:
            releases = self.parse_rlslog(feed.get_input_url('rlslog'), feed)
        except urllib2.HTTPError, e:
            raise ModuleWarning('RlsLog was unable to complete task. HTTPError %s' % (e.code), log)
        except urllib2.URLError, e:
            raise ModuleWarning('RlsLog was unable to complete task. URLError %s' % (e.reason), log)
        except BadStatusLine:
            raise ModuleWarning('RlsLog was unable to complete task. Got BadStatusLine.', log)

        for release in releases:
            # construct entry from release
            entry = Entry()
            def apply_field(d_from, d_to, f):
                if f in d_from:
                    if d_from[f] == None: return # None values are not wanted!
                    d_to[f] = d_from[f]

            for field in ['title', 'url', 'imdb_url', 'imdb_score', 'imdb_votes']:
                apply_field(release, entry, field)

            feed.entries.append(entry)
