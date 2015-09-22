from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.imdb import extract_id
from flexget.utils.cached_input import cached
from flexget.entry import Entry
from flexget.utils.soup import get_soup

log = logging.getLogger('imdb_list')
USER_ID_RE = r'^ur\d{7,8}$'
CUSTOM_LIST_RE = r'^ls\d{7,10}$'
USER_LISTS = ['watchlist', 'ratings', 'checkins']


class ImdbList(object):
    """"Creates an entry for each movie in your imdb list."""

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'string',
                'pattern': USER_ID_RE,
                'error_pattern': 'user_id must be in the form urXXXXXXX'
            },
            'list': {
                'type': 'string',
                'oneOf': [
                    {'enum': USER_LISTS},
                    {'pattern': CUSTOM_LIST_RE}
                ],
                'error_oneOf': 'list must be either %s, or a custom list name (lsXXXXXXXXX)' % ', '.join(USER_LISTS)
            }
        },
        'additionalProperties': False,
        'required': ['list'],
        'anyOf': [
            {'required': ['user_id']},
            {'properties': {'list': {'pattern': CUSTOM_LIST_RE}}}
        ],
        'error_anyOf': 'user_id is required if not using a custom list (lsXXXXXXXXX format)'
    }

    @cached('imdb_list', persist='2 hours')
    def on_task_input(self, task, config):
        # Create movie entries by parsing imdb list page(s) html using beautifulsoup
        log.verbose('Retrieving imdb list: %s' % config['list'])

        params = {'view': 'compact'}
        if config['list'] in ['watchlist', 'ratings', 'checkins']:
            url = 'http://www.imdb.com/user/%s/%s' % (config['user_id'], config['list'])
        else:
            url = 'http://www.imdb.com/list/%s' % config['list']

        log.debug('Requesting: %s' % url)
        page = task.requests.get(url, params=params)
        if page.status_code != 200:
            raise plugin.PluginError('Unable to get imdb list. Either list is private or does not exist.')

        soup = get_soup(page.text)
        # TODO: Something is messed up with the html5lib parser and imdb, have to get to our subsection without
        # recursion before doing a regular find. Repeated in the loop below as well.
        soup = soup.find('div', id='root').find('div', id='pagecontent', recursive=False)
        div = soup.find('div', class_='desc')
        if div:
            total_movie_count = int(div.get('data-size'))
        else:
            total_movie_count = 0

        if total_movie_count == 0:
            log.verbose('No movies were found in imdb list: %s' % config['list'])
            return

        entries = []
        start = 1
        while start < total_movie_count:
            if start == 1:
                trs = soup.find_all(attrs={'data-item-id': True})
            else:
                params['start'] = start
                page = task.requests.get(url, params=params)
                if page.status_code != 200:
                    raise plugin.PluginError('Unable to get imdb list.')
                soup = get_soup(page.text)
                # TODO: This is a hack, see above
                soup = soup.find('div', id='root').find('div', id='pagecontent', recursive=False)
                trs = soup.find_all(attrs={'data-item-id': True})

            for tr in trs:
                a = tr.find('td', class_='title').find('a')
                if not a:
                    log.debug('no title link found for row, skipping')
                    continue
                link = ('http://www.imdb.com' + a.get('href')).rstrip('/')
                entry = Entry()
                entry['title'] = a.string
                try:
                    year = int(tr.find('td', class_='year').string)
                    entry['title'] += ' (%s)' % year
                    entry['imdb_year'] = year
                except ValueError:
                    pass
                entry['url'] = link
                entry['imdb_id'] = extract_id(link)
                entry['imdb_name'] = entry['title']
                entries.append(entry)

            start = len(entries) + 1

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(ImdbList, 'imdb_list', api_ver=2)
