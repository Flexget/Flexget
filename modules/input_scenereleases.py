import urllib2
import logging
import re
from httplib import BadStatusLine
from feed import Entry
from manager import ModuleWarning
from BeautifulSoup import BeautifulSoup

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('scenereleases')

class InputScenereleases:

    """
        Uses scenereleases.info category url as input.

        Example:

        scenereleases: http://www.scenereleases.info/search/label/Movies%20-%20DVD%20Rip
    """

    def register(self, manager, parser):
        manager.register('scenereleases')

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
            votes = f.group(1)
        log.debug("parse_imdb returning score: '%s' votes: '%s' from: '%s'" % (str(score), str(votes), s))
        return (score, votes)

    def parse_site(self, url, feed):
        """Parse configured url and return releases array"""
        
        page = urllib2.urlopen(url)
        soup = BeautifulSoup(page)
            
        releases = []
        for entry in soup.findAll('div', attrs={'id':re.compile('post', re.IGNORECASE)}):
            release = {}
            title = entry.find('h3')
            if not title:
                log.debug('No h3 entrytitle')
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
                if link.has_key('href'):
                    link_href = link['href']
                else:
                    continue
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
                resolver = feed.manager.get_module_by_name('resolver')
                if resolver['instance'].resolvable(feed, temp):
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

    def feed_input(self, feed):
        try:
            releases = self.parse_site(feed.get_input_url('scenereleases'), feed)
        except urllib2.HTTPError, e:
            raise ModuleWarning('scenereleases was unable to complete task. HTTPError %s' % (e.code), log)
        except urllib2.URLError, e:
            raise ModuleWarning('scenereleases was unable to complete task. URLError %s' % (e.reason), log)
        except BadStatusLine:
            raise ModuleWarning('scenereleases was unable to complete task. Got BadStatusLine.', log)

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
