from __future__ import unicode_literals, division, absolute_import
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
    """"Creates an entry for each movie in your Anidb list."""

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'integer',
                'pattern': USER_ID_RE,
                'error_pattern': 'user_id must be in the form XXXXXXX'
            }
        },
        'additionalProperties': False,
        'required': ['user_id'],
        'error_required': 'user_id is required'
    }

    @cached('anidb_list', persist='2 hours')
    def on_task_input(self, task, config):
        # Create movie entries by parsing anidb wishlist page html using beautifulsoup
        log.verbose('Retrieving AniDB list: mywishlist')
        url = 'http://anidb.net/perl-bin/animedb.pl?show=mywishlist&uid=%s' % config['user_id']
        log.debug('Requesting: %s' % url)

        page = task.requests.get(url)
        if page.status_code != 200:
            raise plugin.PluginError('Unable to get AniDB list. Either list is private or does not exist.')

        soup = get_soup(page.text)
        soup = soup.find('table', class_='wishlist')

        trs = soup.find_all('tr')
        if not trs:
            log.verbose('No movies were found in AniDB list: mywishlist')
            return

        entries = []
        for tr in trs:
            if tr.find('span', title='Type: Movie'):
                a = tr.find('label').find('a')
                if not a:
                    log.debug('no title link found for row, skipping')
                    continue
                link = ('http://anidb.net/perl-bin/' + a.get('href'))

                anime_id = ""
                match = re.search(r'aid=([\d]{1,5})', a.get('href'))
                if match:
                    anime_id = match.group(1)

                entry = Entry()
                entry['title'] = a.string
                entry['url'] = link
                entry['anidb_id'] = anime_id
                entry['anidb_name'] = entry['title']
                entries.append(entry)
            else:
               log.verbose('Entry is not a movie')
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(AnidbList, 'anidb_list', api_ver=2)
