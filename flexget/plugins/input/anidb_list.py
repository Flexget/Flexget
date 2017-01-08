from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.entry import Entry
from flexget.utils.soup import get_soup

log = logging.getLogger('anidb_list')
USER_ID_RE = r'^\d{1,6}$'


class AnidbList(object):
    """"Creates an entry for each movie or series in your AniDB wishlist."""

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'integer',
                'pattern': USER_ID_RE,
                'error_pattern': 'user_id must be in the form XXXXXXX'},
            'type': {
                'type': 'string',
                'enum': ['shows', 'movies'],
                'default': 'movies'},
            'strip_dates': {
                'type': 'boolean',
                'default': False}
        },
        'additionalProperties': False,
        'required': ['user_id'],
        'error_required': 'user_id is required'
    }

    @cached('anidb_list', persist='2 hours')
    def on_task_input(self, task, config):
        # Create entries by parsing AniDB wishlist page html using beautifulsoup
        log.verbose('Retrieving AniDB list: mywishlist')
        url = 'http://anidb.net/perl-bin/animedb.pl?show=mywishlist&uid=%s' % config['user_id']
        log.debug('Requesting: %s' % url)

        page = task.requests.get(url)
        if page.status_code != 200:
            raise plugin.PluginError('Unable to get AniDB list. Either the list is private or does not exist.')

        soup = get_soup(page.text)
        soup = soup.find('table', class_='wishlist')

        trs = soup.find_all('tr')
        if not trs:
            log.verbose('No movies were found in AniDB list: mywishlist')
            return

        entries = []
        entry_type = ''
        if config['type'] == 'movies':
            entry_type = 'Type: Movie'
        elif config['type'] == 'shows':
            entry_type = 'Type: TV Series'
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

                link = ('http://anidb.net/perl-bin/' + a.get('href'))

                anime_id = ""
                match = re.search(r'aid=([\d]{1,5})', a.get('href'))
                if match:
                    anime_id = match.group(1)

                entry = Entry()
                entry['title'] = anime_title
                entry['url'] = link
                entry['anidb_id'] = anime_id
                entry['anidb_name'] = entry['title']
                entries.append(entry)
            else:
                log.verbose('Entry does not match the requested type')
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(AnidbList, 'anidb_list', api_ver=2, interfaces=['task'])
