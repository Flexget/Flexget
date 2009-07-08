import urllib2, logging, re
from httplib import BadStatusLine
from flexget.feed import Entry
from flexget.plugin import *
from flexget.utils.log import log_once
from flexget.utils.soup import get_soup
from BeautifulSoup import NavigableString

log = logging.getLogger('rlslog')

class RlsLog:
    """
        Adds support for rlslog.net as a feed.

        In case of movies the plugin supplies pre-parses IMDB-details
        (helps when chaining with filter_imdb).
    """
    def validator(self):
        from flexget import validator
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
        #log.debug("parse_imdb returning score: '%s' votes: '%s' from: '%s'" % (str(score), str(votes), s))
        return (score, votes)

    def parse_rlslog(self, rlslog_url, feed):
        """Parse configured url and return releases array"""
        
        page = urllib2.urlopen(rlslog_url)
        soup = get_soup(page)
            
        releases = []
        for entry in soup.findAll('div', attrs={'class' : 'entry'}):
            release = {}
            h3 = entry.find('h3', attrs={'class' : 'entrytitle'})
            if not h3:
                log.debug('FAIL: No h3 entrytitle')
                continue
            release['title'] = h3.a.contents[0].strip()
            entrybody = entry.find('div', attrs={'class' : 'entrybody'})
            if not entrybody:
                log.debug('FAIL: No entrybody')
                continue

            log.log(5, 'Processing title %s' % (release['title']))

            rating = entrybody.find('strong', text=re.compile('imdb rating\:', re.IGNORECASE))
            if rating != None:
                score_raw = rating.next.string
                if score_raw != None:
                    release['imdb_score'], release['imdb_votes'] = self.parse_imdb(score_raw)
            
            for link in entrybody.findAll('a'):
                if not link.contents:
                    log.log(5, 'link content empty, skipping')
                    continue
                link_name = link.contents[0]
                if link_name == None:
                    continue
                if not isinstance(link_name, NavigableString):
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
                resolver = get_plugin_by_name('resolver')
                if resolver['instance'].resolvable(feed, temp):
                    release['url'] = link_href
                    log.log(5, '--> accepting %s (resolvable)' % link_href)
                else:
                    log.log(5, '<-- ignoring %s (non-resolvable)' % link_href)

            # reject if no torrent link
            if not 'url' in release:
                log_once('%s skipped due to missing or unrecognized download link' % (release['title']), log)
            else:
                releases.append(release)

        return releases

    def feed_input(self, feed):
        url = feed.get_input_url('rlslog')
        if url.endswith('feed/'):
            raise PluginWarning('Invalid URL. Remove trailing feed/ from the url.')
        try:
            releases = self.parse_rlslog(url, feed)
        except urllib2.HTTPError, e:
            raise PluginWarning('RlsLog was unable to complete task. HTTPError %s' % (e.code), log)
        except urllib2.URLError, e:
            raise PluginWarning('RlsLog was unable to complete task. URLError %s' % (e.reason), log)
        except BadStatusLine:
            raise PluginWarning('RlsLog was unable to complete task. Got BadStatusLine.', log)

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

register_plugin(RlsLog, 'rlslog')
