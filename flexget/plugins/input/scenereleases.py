from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.entry import Entry
from flexget.plugin import register_plugin, get_plugin_by_name, internet
from flexget.utils.soup import get_soup
from flexget.utils.cached_input import cached
from bs4 import NavigableString
from flexget.utils.tools import urlopener

log = logging.getLogger('scenereleases')


class InputScenereleases:
    """
    Uses scenereleases.info category url as input.

    Example::

      scenereleases: http://scenereleases.info/category/movies/movies-dvd-rip
    """

    def validator(self):
        from flexget import validator
        return validator.factory('url')

    def parse_site(self, url, task):
        """Parse configured url and return releases array"""

        page = urlopener(url, log)
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
                    release['imdb_url'] = link_href

                # test if entry with this url would be rewritable by known plugins (ie. downloadable)
                temp = {}
                temp['title'] = release['title']
                temp['url'] = link_href
                urlrewriting = get_plugin_by_name('urlrewriting')
                if urlrewriting['instance'].url_rewritable(task, temp):
                    release['url'] = link_href
                    log.trace('--> accepting %s (resolvable)' % link_href)
                else:
                    log.trace('<-- ignoring %s (non-resolvable)' % link_href)

            # reject if no torrent link
            if not 'url' in release:
                from flexget.utils.log import log_once
                log_once('%s skipped due to missing or unsupported (unresolvable) download link' % (release['title']), log)
            else:
                releases.append(release)

        return releases

    @cached('scenereleases')
    @internet(log)
    def on_task_input(self, task, config):
        releases = self.parse_site(config, task)
        entries = []

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

            entries.append(entry)

        return entries

register_plugin(InputScenereleases, 'scenereleases', api_ver=2)
