from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from bs4 import NavigableString
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.imdb import extract_id
from flexget.utils.soup import get_soup

log = logging.getLogger('sceper')


class InputSceper(object):
    """
    Uses sceper.ws category url as input.

    Example::

      sceper: http://sceper.ws/category/movies/movies-dvd-rip
    """

    schema = {'type': 'string', 'format': 'url'}

    def parse_site(self, url, task):
        """Parse configured url and return releases array"""

        try:
            page = task.requests.get(url).content
        except RequestException as e:
            raise plugin.PluginError('Error getting input page: %s' % e)
        soup = get_soup(page)

        releases = []
        for entry in soup.find_all('div', attrs={'class': 'entry'}):
            release = {}
            title = entry.find('h2')
            if not title:
                log.debug('No h2 entrytitle')
                continue
            release['title'] = title.a.contents[0].strip()

            log.debug('Processing title %s' % (release['title']))

            for link in entry.find_all('a'):
                # no content in the link
                if not link.contents:
                    continue
                link_name = link.contents[0]
                if link_name is None:
                    continue
                if not isinstance(link_name, NavigableString):
                    continue
                link_name = link_name.strip().lower()
                if link.has_attr('href'):
                    link_href = link['href']
                else:
                    continue
                log.debug('found link %s -> %s' % (link_name, link_href))
                # handle imdb link
                if link_name.lower() == 'imdb':
                    log.debug('found imdb link %s' % link_href)
                    release['imdb_id'] = extract_id(link_href)

                # test if entry with this url would be rewritable by known plugins (ie. downloadable)
                temp = {}
                temp['title'] = release['title']
                temp['url'] = link_href
                urlrewriting = plugin.get_plugin_by_name('urlrewriting')
                if urlrewriting['instance'].url_rewritable(task, temp):
                    release['url'] = link_href
                    log.trace('--> accepting %s (resolvable)' % link_href)
                else:
                    log.trace('<-- ignoring %s (non-resolvable)' % link_href)

            # reject if no torrent link
            if 'url' not in release:
                from flexget.utils.log import log_once
                log_once('%s skipped due to missing or unsupported (unresolvable) download link' % (release['title']),
                         log)
            else:
                releases.append(release)

        return releases

    @cached('sceper')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        releases = self.parse_site(config, task)
        return [Entry(release) for release in releases]


@event('plugin.register')
def register_plugin():
    plugin.register(InputSceper, 'sceper', api_ver=2)
