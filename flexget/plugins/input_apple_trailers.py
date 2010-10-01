import logging
import re
import string
import urllib2
from flexget.feed import Entry
from input_rss import InputRSS
from flexget.plugin import *
from flexget.utils.tools import urlopener
from flexget.utils.soup import get_soup

log = logging.getLogger('apple_trailers')


class AppleTrailers(InputRSS):
    """
        Adds support for Apple.com movie trailers.

        apple_trailers: 480p

        Choice of quality if one of: ipod, 320, 480, 640w, 480p, 720p, 1080p
    """

    def __init__(self):
        self.rss_url = 'http://trailers.apple.com/trailers/home/rss/newtrailers.rss'
        self.qualities = ['ipod', '320', '480', '640w', '480p', '720p', '1080p']

    def validator(self):
        from flexget import validator
        config = validator.factory()
        # TODO: 320 and 480 need to be quoted. is it possible to validate
        # without the need for quotes?
        config.accept('choice').accept_choices(self.qualities, ignore_case=True)
        return config

    def on_feed_start(self, feed):
        feed.config['rss'] = self.rss_url
        feed.config['headers'] = {'User-Agent': 'QuickTime/7.6.6'}
        self.quality = feed.config['apple_trailers']

    @priority(127)
    def on_feed_input(self, feed):
        super(AppleTrailers, self).on_feed_input(feed)

        # Multiple entries can point to the same movie page (trailer 1, clip
        # 1, etc.)
        entries = {}
        for entry in feed.entries:
            url = entry['original_url']
            if url in entries:
                continue
            else:
                title = entry['title']
                entries[url] = title[:title.rfind('-')].rstrip()

        feed.entries = []

        for url, title in entries.iteritems():
            inc_url = url + 'includes/playlists/web.inc'
            page = urlopener(inc_url, log)

            soup = get_soup(page)
            links = soup.findAll('a', attrs={'class': 'target-quicktimeplayer', 'href': re.compile(r'_480p\.mov$')})
            for link in links:
                url = link.get('href')
                url = url[:url.rfind('_')]
                quality = self.quality.lower()

                if 'ipod' == quality:
                    url += '_i320.m4v'
                else:
                    url += '_h' + quality + '.mov'

                entry = Entry()
                entry['url'] = url
                entry['title'] = title

                match = re.search(r'.*/([^?#]*)', url)
                entry['filename'] = match.group(1)

                feed.entries.append(entry)
                log.debug('found trailer %s', url)

register_plugin(AppleTrailers, 'apple_trailers')
