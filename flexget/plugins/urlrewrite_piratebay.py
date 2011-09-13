import re
import urllib
import logging
import difflib
from plugin_urlrewriting import UrlRewritingError
from flexget.feed import Entry
from flexget.plugin import register_plugin, internet, PluginWarning
from flexget.utils.tools import urlopener
from flexget.utils.soup import get_soup
from flexget.utils.titles.parser import TitleParser

log = logging.getLogger('piratebay')


class UrlRewritePirateBay(object):
    """PirateBay urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, feed, entry):
        url = entry['url']
        if url.endswith('.torrent'):
            return False
        if url.startswith('http://thepiratebay.org/'):
            return True
        if url.startswith('http://torrents.thepiratebay.org/'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, feed, entry):
        if not 'url' in entry:
            log.error("Didn't actually get a URL...")
        else:
            log.debug("Got the URL: %s" % entry['url'])
        if entry['url'].startswith('http://thepiratebay.org/search/'):
            # use search
            try:
                entry['url'] = self.search_title(entry['title'])[0]['url']
            except PluginWarning, e:
                raise UrlRewritingError(e)
        else:
            # parse download page
            entry['url'] = self.parse_download_page(entry['url'])

    @internet(log)
    def parse_download_page(self, url):
        page = urlopener(url, log)
        try:
            soup = get_soup(page)
            tag_div = soup.find('div', attrs={'class': 'download'})
            if not tag_div:
                raise UrlRewritingError('Unable to locate download link from url %s' % url)
            tag_a = tag_div.find('a')
            torrent_url = tag_a.get('href')
            return torrent_url
        except Exception, e:
            raise UrlRewritingError(e)

    # search API
    def search(self, query, config=None):
        entries = self.search_title(query)
        log.debug('search got %d results' % len(entries))
        return entries

    # TODO: Put this somewhere for all search plugins
    def clean_name(self, name):
        result = name.lower()
        result = TitleParser.remove_words(result, TitleParser.sounds + TitleParser.codecs)
        result = re.sub('[ \(\)\-_\[\]\.]+', ' ', result)
        return result

    @internet(log)
    def search_title(self, name, url=None):
        """
            Search for name from piratebay.
            If optional search :url: is passed it will be used instead of internal search.
        """

        name = name.replace('.', ' ').lower()
        if not url:
            url = 'http://thepiratebay.org/search/' + urllib.quote(name)
            log.debug('Using %s as piratebay search url' % url)
        page = urlopener(url, log)

        # do this here so I don't have to do it constantly below.
        clean_name = self.clean_name(name)

        soup = get_soup(page)
        entries = []
        comparator = difflib.SequenceMatcher(lambda x: x in ' ', clean_name)
        for link in soup.findAll('a', attrs={'class': 'detLink'}):
            clean_found = self.clean_name(link.contents[0])
            # assign confidence score of how close this link is to the name you're looking for. .6 and above is "close"
            comparator.set_seq2(clean_found)
            confidence = comparator.ratio()
            log.debug('name: %s' % clean_name)
            log.debug('found name: %s' % clean_found)
            log.debug('confidence: %s' % confidence)
            if confidence < 0.7:
                continue
            entry = Entry()
            entry['title'] = link.contents[0]
            entry['url'] = 'http://thepiratebay.org' + link.get('href')
            tds = link.parent.parent.parent.findAll('td')
            entry['torrent_seeds'] = int(tds[-2].contents[0])
            entry['torrent_leeches'] = int(tds[-1].contents[0])
            # Parse content_size
            size = link.findNext(attrs={'class': 'detDesc'}).contents[0]
            size = re.search('Size ([\.\d]+)\xa0([GMK])iB', size)
            if size:
                if size.group(2) == 'G':
                    entry['content_size'] = int(float(size.group(1)) * 1000 ** 3 / 1024 ** 2)
                elif size.group(2) == 'M':
                    entry['content_size'] = int(float(size.group(1)) * 1000 ** 2 / 1024 ** 2)
                else:
                    entry['content_size'] = int(float(size.group(1)) * 1000 / 1024 ** 2)
            entries.append(entry)

        if not entries:
            dashindex = name.rfind('-')
            if dashindex != -1:
                return self.search_title(name[:dashindex])
            else:
                raise PluginWarning('No close matches for %s' % name, log, log_once=True)

        def score(a):
            return a['torrent_seeds'] * 2 + a['torrent_leeches']

        entries.sort(reverse=True, key=score)

        #for torrent in torrents:
        #    log.debug('%s link: %s' % (torrent, torrent['link']))

        return entries

register_plugin(UrlRewritePirateBay, 'piratebay', groups=['urlrewriter', 'search'])
