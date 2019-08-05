from __future__ import unicode_literals, division, absolute_import

import logging
import re
import time
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.log import log_once
from flexget.utils.soup import get_soup

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.imdb.utils import extract_id
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='imdb')


log = logging.getLogger('rlslog')


class RlsLog(object):
    """
    Adds support for rlslog.net as a feed.
    """

    schema = {'type': 'string', 'format': 'url'}

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

            # find imdb url
            link_imdb = entrybody.find('a', text=re.compile(r'imdb', re.IGNORECASE))
            if link_imdb:
                release['imdb_id'] = extract_id(link_imdb['href'])
                release['imdb_url'] = link_imdb['href']

            # find google search url
            google = entrybody.find('a', href=re.compile(r'google', re.IGNORECASE))
            if google:
                release['url'] = google['href']
                releases.append(release)
            else:
                log_once(
                    '%s skipped due to missing or unsupported download link' % (release['title']),
                    log,
                )

        return releases

    @cached('rlslog')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        url = config
        if url.endswith('feed/'):
            raise plugin.PluginError('Invalid URL. Remove trailing feed/ from the url.')

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
                    log.verbose(
                        'Error receiving content, retrying in 5s. Try [%s of 2]. Error: %s'
                        % (number + 1, e)
                    )
                    time.sleep(5)

        # Construct entry from release
        for release in releases:
            entry = Entry()

            def apply_field(d_from, d_to, f):
                if f in d_from:
                    if d_from[f] is None:
                        return  # None values are not wanted!
                    d_to[f] = d_from[f]

            for field in ('title', 'url', 'imdb_url'):
                apply_field(release, entry, field)

            entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(RlsLog, 'rlslog', api_ver=2)
