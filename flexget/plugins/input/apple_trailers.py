from __future__ import unicode_literals, division, absolute_import
import logging
import re
from urllib2 import HTTPError
from flexget.entry import Entry
from flexget.plugin import priority, register_plugin, get_plugin_by_name, DependencyError
from flexget.utils.cached_input import cached
from flexget.utils.tools import urlopener
from flexget.utils.soup import get_soup
try:
    from flexget.plugins.input.rss import InputRSS
except ImportError:
    raise DependencyError(issued_by='apple_trailers', missing='rss')

log = logging.getLogger('apple_trailers')


class AppleTrailers(InputRSS):
    """
        Adds support for Apple.com movie trailers.

        apple_trailers: 480p

        Choice of quality is one of: ipod, '320', '480', 640w, 480p, 720p, 1080p
    """

    rss_url = 'http://trailers.apple.com/trailers/home/rss/newtrailers.rss'
    qualities = ['ipod', 320, '320', 480, '480', '640w', '480p', '720p', '1080p']

    schema = {"enum": qualities}

    # Run before headers plugin
    @priority(135)
    def on_task_start(self, task, config):
        # TODO: Resolve user-agent in a way that doesn't involve modifying the task config.
        # make sure we have dependencies available, will throw DependencyError if not
        get_plugin_by_name('headers')
        # configure them
        task.config['headers'] = {'User-Agent': 'QuickTime/7.6.6'}
        self.quality = str(config)

    @priority(127)
    @cached('apple_trailers')
    def on_task_input(self, task, config):
        # use rss plugin
        rss_config = {'url': self.rss_url}
        rss_entries = super(AppleTrailers, self).on_task_input(task, rss_config)

        # Multiple entries can point to the same movie page (trailer 1, clip
        # 1, etc.)
        entries = {}
        for entry in rss_entries:
            url = entry['original_url']
            if url in entries:
                continue
            else:
                title = entry['title']
                entries[url] = title[:title.rfind('-')].rstrip()

        result = []

        for url, title in entries.iteritems():
            inc_url = url + 'includes/playlists/web.inc'
            try:
                page = urlopener(inc_url, log)
            except HTTPError, err:
                log.warning("HTTPError when opening playlist page: %d %s" % (err.code, err.reason))
                continue

            soup = get_soup(page)
            links = soup.find_all('a', attrs={'class': 'target-quicktimeplayer', 'href': re.compile(r'_h?480p\.mov$')})
            for link in links:
                url = link.get('href')
                url = url[:url.rfind('_')]
                quality = self.quality.lower()

                if quality == 'ipod':
                    url += '_i320.m4v'
                else:
                    url += '_h' + quality + '.mov'

                entry = Entry()
                entry['url'] = url
                entry['title'] = title

                match = re.search(r'.*/([^?#]*)', url)
                entry['filename'] = match.group(1)

                result.append(entry)
                log.debug('found trailer %s', url)

        return result

register_plugin(AppleTrailers, 'apple_trailers', api_ver=2)
