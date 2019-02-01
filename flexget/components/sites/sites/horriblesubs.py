from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

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
    def horrible_get_downloads(requests, title, page_url):
        entries = []

        try:
            soup = get_soup(requests.get(page_url).content)
        except RequestException as e:
            log.error('HorribleSubs request failed: %s', e)
            return entries
        for div in soup.findAll('div', attrs={'class': 'rls-link'}):
            ttitle = '{0} [{1}]'.format(title, re.sub(r'.*-', '', div['id']))
            urls = []
            for url in div.findAll('a'):
                # skip non torrent based links
                if (
                    'hs-ddl-link' in url.parent.attrs['class']
                    or 'hs-xdcc-link' in url.parent.attrs['class']
                ):
                    continue
                log.debug('Found url `%s`', url)
                urls.append(url.attrs['href'])
            # move magnets to last, a bit hacky
            for url in urls[:]:
                if url.startswith('magnet'):
                    urls.remove(url)
                    urls.append(url)
            entries.append(Entry(title=ttitle, url=urls[0], urls=urls))
        return entries

    @staticmethod
    def horrible_entries(requests, page_url):
        entries = []

        try:
            soup = get_soup(requests.get(page_url).content)
        except RequestException as e:
            log.error('HorribleSubs request failed: %s', e)
            return entries

        for li_label in soup.findAll('li'):
            title = '[HorribleSubs] {0}{1}'.format(
                str(li_label.find('span').next_sibling), str(li_label.find('strong').text)
            )
            log.debug('Found title `%s`', title)
            url = li_label.find('a')['href']
            episode = re.sub(r'.*#', '', url)
            # Get show ID
            try:
                soup = get_soup(requests.get('https://horriblesubs.info/{0}'.format(url)).content)
            except RequestException as e:
                log.error('HorribleSubs request failed: %s', e)
                return entries
            show_id = re.sub(r'[^0-9]', '', soup(text=re.compile('hs_showid'))[0])
            entries = HorribleSubs.horrible_get_downloads(
                requests,
                title,
                'https://horriblesubs.info/api.php?method=getshows&type=show&mode=filter&showid={0}&value={1}'.format(
                    show_id, episode
                ),
            )
        return entries

    @staticmethod
    def scraper():
        try:
            import cfscrape
        except ImportError as e:
            log.debug('Error importing cfscrape: %s', e)
            raise plugin.DependencyError(
                'cfscraper', 'cfscrape', 'cfscrape module required. ImportError: %s' % e
            )
        else:
            return cfscrape.create_scraper()

    @cached('horriblesubs')
    def on_task_input(self, task, config):
        if not config:
            return
        scraper = HorribleSubs.scraper()
        return HorribleSubs.horrible_entries(
            scraper, 'https://horriblesubs.info/api.php?method=getlatest'
        )

    # Search API method
    def search(self, task, entry, config):
        if not config:
            return
        entries = []
        scraper = HorribleSubs.scraper()
        for search_string in entry.get('search_strings', [entry['title']]):
            log.debug('Searching `%s`', search_string)
            results = HorribleSubs.horrible_entries(
                scraper,
                'https://horriblesubs.info/api.php?method=search&value={0}'.format(search_string),
            )
            entries.extend(results)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(HorribleSubs, 'horriblesubs', interfaces=['task', 'search'], api_ver=2)
