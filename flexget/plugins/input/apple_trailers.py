from __future__ import unicode_literals, division, absolute_import
import logging
import urlparse
import re

from flexget.entry import Entry
from flexget.plugin import priority, register_plugin, get_plugin_by_name, DependencyError
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException
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

        Choice of quality is one of: 480p, 720p
    """

    rss_url = 'http://trailers.apple.com/trailers/home/rss/newtrailers.rss'
    qualities = ['480p', '720p']

    schema = {'enum': qualities}

    # Run before headers plugin
    @priority(135)
    def on_task_start(self, task, config):
        # TODO: Resolve user-agent in a way that doesn't involve modifying the task config.
        # make sure we have dependencies available, will throw DependencyError if not
        get_plugin_by_name('headers')
        # configure them
        task.config['headers'] = {'User-Agent': 'QuickTime/7.6.6'}

    @priority(127)
    @cached('apple_trailers')
    def on_task_input(self, task, config):
        # use rss plugin
        # since we have to do 2 page lookups per trailer, use all_entries False to lighten load
        rss_config = {'url': self.rss_url, 'all_entries': False}
        rss_entries = super(AppleTrailers, self).on_task_input(task, rss_config)

        # Multiple entries can point to the same movie page (trailer 1, clip1, etc.)
        trailers = {}
        for entry in rss_entries:
            url = entry['original_url']
            trailers.setdefault(url, []).append(entry['title'])

        result = []
        if config == '720p':
            url_extension = 'includes/extralarge.html'
        else:
            url_extension = 'includes/large.html'
        for url, titles in trailers.iteritems():
            inc_url = url + url_extension
            try:
                page = task.requests.get(inc_url)
            except RequestException as err:
                log.warning("RequestsException when opening playlist page: %s" % err)
                continue

            soup = get_soup(page.text)
            for title in titles:
                trailer = soup.find(text=title.split(' - ')[1])
                if not trailer:
                    log.debug('did not find trailer link')
                    continue
                trailers_link = trailer.find_parent('a')
                if not trailers_link:
                    log.debug('did not find trailer link')
                    continue
                try:
                    page = task.requests.get(urlparse.urljoin(url, trailers_link['href']))
                except RequestException as e:
                    log.debug('error getting trailers page')
                    continue
                trailer_soup = get_soup(page.text)
                link = trailer_soup.find('a', attrs={'class': 'movieLink'})
                if not link:
                    log.debug('could not find download link')
                    continue
                # Need to add an 'h' in front of the resolution
                entry_url = link['href']
                entry_url = entry_url[:entry_url.find(config + '.mov')] + 'h%s.mov' % config
                entry = Entry(title, entry_url)
                # Populate a couple entry fields for making pretty filenames
                entry['movie_name'], entry['apple_trailers_name'] = title.split(' - ')
                result.append(entry)

        return result

register_plugin(AppleTrailers, 'apple_trailers', api_ver=2)
