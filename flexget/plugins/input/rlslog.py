from __future__ import unicode_literals, division, absolute_import
import logging
import time
from requests import RequestException
from bs4 import NavigableString
from flexget.entry import Entry
from flexget.plugin import register_plugin, internet, get_plugin_by_name, PluginError
from flexget.utils.log import log_once
from flexget.utils.soup import get_soup
from flexget.utils.cached_input import cached

log = logging.getLogger('rlslog')


class RlsLog(object):
    """
    Adds support for rlslog.net as a feed.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('url')

    def parse_rlslog(self, rlslog_url, task):
        """
        :param rlslog_url: Url to parse from
        :param task: Task instance
        :return: List of release dictionaries
        """

        # BeautifulSoup doesn't seem to work if data is already decoded to unicode :/
        soup = get_soup(task.requests.get(rlslog_url, timeout=25).content)

        releases = []
        for entry in soup.find_all('div', attrs={'class': 'entry'}):
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

            log.trace('Processing title %s' % (release['title']))

            for link in entrybody.find_all('a'):
                if not link.contents:
                    log.trace('link content empty, skipping')
                    continue
                if not link.has_attr('href'):
                    log.trace('link %s missing href' % link)
                    continue

                link_name = link.contents[0]
                link_name_ok = True
                if link_name is None:
                    log.trace('link_name is none')
                    link_name_ok = False
                if not isinstance(link_name, NavigableString):
                    log.trace('link_name is not NavigableString')
                    link_name_ok = False

                link_href = link['href']

                # parse imdb link
                if link_name_ok:
                    link_name = link_name.strip().lower()
                    if link_name == 'imdb':
                        release['imdb_url'] = link_href

                # test if entry with this url would be recognized
                temp = {'title': release['title'], 'url': link_href}
                urlrewriting = get_plugin_by_name('urlrewriting')
                if urlrewriting['instance'].url_rewritable(task, temp):
                    release['url'] = link_href
                    log.trace('--> accepting %s (known url pattern)' % link_href)
                else:
                    log.trace('<-- ignoring %s (unknown url pattern)' % link_href)

            # reject if no torrent link
            if not 'url' in release:
                log_once('%s skipped due to missing or unsupported download link' % (release['title']), log)
            else:
                releases.append(release)

        return releases

    @cached('rlslog')
    @internet(log)
    def on_task_input(self, task, config):
        url = config
        if url.endswith('feed/'):
            raise PluginError('Invalid URL. Remove trailing feed/ from the url.')

        releases = []
        entries = []

        # retry rlslog (badly responding) up to 4 times (requests tries 2 times per each of our tries here)
        for number in range(2):
            try:
                releases = self.parse_rlslog(url, task)
                break
            except RequestException as e:
                if number == 1:
                    raise
                else:
                    log.verbose('Error receiving content, retrying in 5s. Try [%s of 2]. Error: %s' % (number + 1, e))
                    time.sleep(5)

        # Construct entry from release
        for release in releases:
            entry = Entry()

            def apply_field(d_from, d_to, f):
                if f in d_from:
                    if d_from[f] is None:
                        return # None values are not wanted!
                    d_to[f] = d_from[f]

            for field in ('title', 'url', 'imdb_url'):
                apply_field(release, entry, field)

            entries.append(entry)

        return entries

register_plugin(RlsLog, 'rlslog', api_ver=2)
