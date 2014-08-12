from __future__ import unicode_literals, division, absolute_import
import logging
import re
import feedparser
import math
from flexget import plugin
from flexget.event import event
from flexget.utils.imdb import extract_id
from flexget.utils.cached_input import cached
from flexget.entry import Entry
from flexget.utils.soup import get_soup

log = logging.getLogger('imdb_list')
USER_ID_RE = r'^ur\d{7,8}$'


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
            'list': {'type': 'string'}
        },
        'required': ['list', 'user_id'],
        'additionalProperties': False
    }

    @cached('imdb_list', persist='2 hours')
    def on_task_input(self, task, config):
        # Create movie entries by parsing imdb list page(s) html using beautifulsoup
        log.verbose('Retrieving list: %s...' % config['list'])

        params = {'view': 'compact'}
        if config['list'] in ['watchlist', 'ratings', 'checkins']:
            url = 'http://www.imdb.com/user/%s/%s' % (config['user_id'], config['list'])
        else:
            url = 'http://www.imdb.com/list/%s' % config['list']

        log.debug('Requesting: %s' % url)
        page = task.requests.get(url, params=params)
        if page.status_code != 200:
            raise plugin.PluginError('Unable to get imdb list. Either list is private or does not exist.')

        soup = get_soup(page.text, 'html.parser')
        div = soup.find('div', class_='desc')
        if div:
            total_movie_count = int(div.get('data-size'))
        else:
            total_movie_count = 0

        if total_movie_count == 0:
            log.verbose('No movies were found in imdb list.')
            return

        entries = []
        for start_movie in xrange(1, total_movie_count + 1, 250):
            if start_movie > 250:
                params['start'] = start_movie
                page = task.requests.get(url, params=params)
                if page.status_code != 200:
                    raise plugin.PluginError('Unable to get imdb list.')
                soup = get_soup(page.text, 'html.parser')

            trs = soup.find_all(attrs={'data-item-id': True})
            for tr in trs:
                a = tr.find('td', class_='title').find('a')
                link = ('http://www.imdb.com' + a.get('href')).rstrip('/')
                year = tr.find('td', class_='year').string
                entry = Entry()
                entry['title'] = a.string + ' (' + year + ')'
                entry['imdb_year'] = int(year)
                entry['url'] = link
                entry['imdb_id'] = extract_id(link)
                entry['imdb_name'] = entry['title']
                entries.append(entry)

        return entries

@event('plugin.register')
def register_plugin():
    plugin.register(ImdbList, 'imdb_list', api_ver=2)
