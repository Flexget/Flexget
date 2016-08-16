from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup

log = logging.getLogger('horriblesubs')


class HorribleSubs(object):
    """
    Give latest horriblesubs releases
    """
    schema = {'type': 'boolean'}

    @staticmethod
    def horrible_entries(requests, page_url):
        entries = []

        try:
            soup = get_soup(requests.get(page_url).content)
        except RequestException as e:
            log.error('HorribleSubs request failed: %s', e)
            return entries

        for td_label in soup.findAll('td', attrs={'class': 'dl-label'}):
            title = '[HorribleSubs] {0}'.format(str(td_label.find('i').string))
            urls = []
            log.debug('Found title `{0}`'.format(title))
            for span in td_label.parent.findAll('span', attrs={'class': 'dl-link'}):
                # skip non torrent based links
                if 'hs-ddl-link' in span.parent.attrs['class']:
                    continue
                url = str(span.find('a').attrs['href'])
                log.debug('Found url `{0}`'.format(url))
                urls.append(url)
            # move magnets to last, a bit hacky
            for url in urls[:]:
                if url.startswith('magnet'):
                    urls.remove(url)
                    urls.append(url)
            entries.append(Entry(title=title, url=urls[0], urls=urls))
        return entries

    @cached('horriblesubs')
    def on_task_input(self, task, config):
        if not config:
            return
        return HorribleSubs.horrible_entries(
            task.requests, 'http://horriblesubs.info/lib/latest.php')

    def search(self, task, entry, config):
        if not config:
            return
        entries = []
        for search_string in entry.get('search_strings', [entry['title']]):
            log.debug('Searching `{0}`'.format(search_string))
            results = HorribleSubs.horrible_entries(
                task.requests, 'http://horriblesubs.info/lib/search.php?value={0}'.format(search_string))
            entries.extend(results)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(HorribleSubs, 'horriblesubs', groups=['search'], api_ver=2)
