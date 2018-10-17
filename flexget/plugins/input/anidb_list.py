from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.entry import Entry
from flexget.utils.soup import get_soup

log = logging.getLogger('anidb_list')
USER_ID_RE = r'^\d{1,6}$'


class AnidbList(object):
    """"Creates an entry for each movie or series in your AniDB wishlist."""

    anidb_url = 'http://anidb.net/perl-bin/'

    default_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36 (KHTML, like Gecko) ' \
                         'Chrome/69.0.3497.100 Safari/537.36'

    MODE_MAP = {
        'all': 0,
        'undefined': 1,
        'watch': 2,
        'get': 3,
        'blacklist': 4,
        'buddy': 11
    }

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'integer',
                'pattern': USER_ID_RE,
                'error_pattern': 'user_id must be in the form XXXXXXX'},
            'type': {
                'type': 'string',
                'enum': ['shows', 'movies', 'ovas'],
                'default': 'movies'},
            'mode': {
                'type': 'string',
                'enum': list(MODE_MAP.keys()),
                'default': 'all'},
            'pass': {
                'type': 'string'},
            'strip_dates': {
                'type': 'boolean',
                'default': False}
        },
        'additionalProperties': False,
        'required': ['user_id'],
        'error_required': 'user_id is required'
    }

    def __build_url(self, config):
        base_url = self.anidb_url + 'animedb.pl?show=mywishlist&uid=%s' % config['user_id']
        base_url = base_url +\
            ('' if config['mode'] == 'all' else '&mode=%s' % config['mode'])
        base_url = base_url + ('' if config['pass'] is None else '&pass=%s' % config['pass'])
        return base_url

    @cached('anidb_list', persist='2 hours')
    def on_task_input(self, task, config):
        # Create entries by parsing AniDB wishlist page html using beautifulsoup
        log.verbose('Retrieving AniDB list: mywishlist:%s', config['mode'])
        comp_link = self.__build_url(config)
        log.debug('Requesting: %s', comp_link)

        task_headers = task.requests.headers
        task_headers['User-Agent'] = self.default_user_agent

        try:
            page = task.requests.get(comp_link, headers=task_headers)
        except RequestException as e:
            raise plugin.PluginError(str(e))
        if page.status_code != 200:
            raise plugin.PluginError('Unable to get AniDB list. Either the list is private or does not exist.')

        entries = []
        entry_type = ''

        if config['type'] == 'movies':
            entry_type = 'Type: Movie'
        elif config['type'] == 'shows':
            entry_type = 'Type: TV Series'
        elif config['type'] == 'ovas':
            entry_type = 'Type: OVA'

        while True:
            soup = get_soup(page.text)
            soup_table = soup.find('table', class_='wishlist').find('tbody')

            trs = soup_table.find_all('tr')
            if not trs:
                log.verbose('No movies were found in AniDB list: mywishlist')
                return entries
            for tr in trs:
                if tr.find('span', title=entry_type):
                    a = tr.find('td', class_='name').find('a')
                    if not a:
                        log.debug('No title link found for the row, skipping')
                        continue

                    anime_title = a.string
                    if config.get('strip_dates'):
                        # Remove year from end of series name if present
                        anime_title = re.sub(r'\s+\(\d{4}\)$', '', anime_title)

                    entry = Entry()
                    entry['title'] = anime_title
                    entry['url'] = (self.anidb_url + a.get('href'))
                    entry['anidb_id'] = tr['id'][1:]  # The <tr> tag's id is "aN..." where "N..." is the anime id
                    log.debug('%s id is %s', entry['title'], entry['anidb_id'])
                    entry['anidb_name'] = entry['title']
                    entries.append(entry)
                else:
                    log.verbose('Entry does not match the requested type')
            try:
                # Try to get the link to the next page.
                next_link = soup.find('li', class_='next').find('a')['href']
            except TypeError:
                # If it isn't there, there are no more pages to be crawled.
                log.verbose('No more pages on the wishlist.')
                break
            comp_link = self.anidb_url + next_link
            log.debug('Requesting: %s', comp_link)
            try:
                page = task.requests.get(comp_link, headers=task_headers)
            except RequestException as e:
                log.error(str(e))
            if page.status_code != 200:
                log.warning('Unable to retrieve next page of wishlist.')
                break
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(AnidbList, 'anidb_list', api_ver=2, interfaces=['task'])
