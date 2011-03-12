import urllib2
import logging
import re
from flexget.feed import Entry
from flexget.plugin import *
from flexget.utils.log import log_once
from flexget.utils.soup import get_soup
from flexget.utils.cached_input import cached
from BeautifulSoup import NavigableString
from flexget.utils.tools import urlopener

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
        re_score = [re.compile('(\d\.\d)'), re.compile('(\d)/10')]
        for r in re_score:
            f = r.search(s)
            if f is not None:
                score = float(f.group(1))
                break
        f = re_votes.search(s.replace(',', ''))
        if f is not None:
            votes = int(f.group(1))
        #log.debug("parse_imdb returning score: '%s' votes: '%s' from: '%s'" % (str(score), str(votes), s))
        return (score, votes)

    def parse_rlslog(self, rlslog_url, feed):
        """Parse configured url and return releases array"""

        page = urlopener(rlslog_url, log)
        soup = get_soup(page)

        releases = []
        for entry in soup.findAll('div', attrs={'class': 'entry'}):
            release = {}
            h3 = entry.find('h3', attrs={'class': 'entrytitle'})
            if not h3:
                log.debug('FAIL: No h3 entrytitle')
                continue
            release['title'] = h3.a.contents[0].strip()
            entrybody = entry.find('div', attrs={'class': 'entrybody'})
            if not entrybody:
                log.debug('FAIL: No entrybody')
                continue

            log.debugall('Processing title %s' % (release['title']))

            rating = entrybody.find('strong', text=re.compile(r'imdb rating:', re.IGNORECASE))
            if rating is not None:
                score_raw = rating.next.string
                if score_raw is not None:
                    release['imdb_score'], release['imdb_votes'] = self.parse_imdb(score_raw)

            for link in entrybody.findAll('a'):
                if not link.contents:
                    log.debugall('link content empty, skipping')
                    continue
                if not link.has_key('href'):
                    log.debugall('link %s missing href' % link)
                    continue

                link_name = link.contents[0]
                link_name_ok = True
                if link_name is None:
                    log.debugall('link_name is none')
                    link_name_ok = False
                if not isinstance(link_name, NavigableString):
                    log.debugall('link_name is NavigableString')
                    link_name_ok = False

                link_href = link['href']

                # parse imdb link
                if link_name_ok:
                    link_name = link_name.strip().lower()
                    if link_name == 'imdb':
                        release['imdb_url'] = link_href
                        score_raw = link.next.next.string
                        if not 'imdb_score' in release and not 'imdb_votes' in release and score_raw is not None:
                            release['imdb_score'], release['imdb_votes'] = self.parse_imdb(score_raw)

                # test if entry with this url would be recognized
                temp = {}
                temp['title'] = release['title']
                temp['url'] = link_href
                urlrewriting = get_plugin_by_name('urlrewriting')
                if urlrewriting['instance'].url_rewritable(feed, temp):
                    release['url'] = link_href
                    log.debugall('--> accepting %s (known url pattern)' % link_href)
                else:
                    log.debugall('<-- ignoring %s (unknown url pattern)' % link_href)

            # reject if no torrent link
            if not 'url' in release:
                log_once('%s skipped due to missing or unsupported (unresolvable) download link' % (release['title']), log)
            else:
                releases.append(release)

        return releases

    @cached('rlslog', 'url')
    @internet(log)
    def on_feed_input(self, feed):
        url = feed.get_input_url('rlslog')
        if url.endswith('feed/'):
            raise PluginWarning('Invalid URL. Remove trailing feed/ from the url.')

        releases = []

        # retry rlslog (badly responding) up to 6 times (our urlopener tries 3 times per each of our tries here)
        for number in range(2):
            try:
                releases = self.parse_rlslog(url, feed)
            except urllib2.HTTPError, e:
                if number == 1:
                    raise
                else:
                    import time
                    feed.verbose_progress('Error recieving content, retrying in 5s. Try [%s of 3]. HTTP Error Code: %s' % (str(number + 1), str(e.code)))
                    time.sleep(5)
            except urllib2.URLError, e:
                if number == 2:
                    raise
                else:
                    import time
                    feed.verbose_progress('Error retrieving the URL, retrying in 5s. Try [%s of 3]. Error: %s' % (str(number + 1), str(e.reason)))
                    time.sleep(5)

        for release in releases:
            # construct entry from release
            entry = Entry()

            def apply_field(d_from, d_to, f):
                if f in d_from:
                    if d_from[f] is None:
                        return # None values are not wanted!
                    d_to[f] = d_from[f]

            for field in ['title', 'url', 'imdb_url', 'imdb_score', 'imdb_votes']:
                apply_field(release, entry, field)

            feed.entries.append(entry)

register_plugin(RlsLog, 'rlslog')
