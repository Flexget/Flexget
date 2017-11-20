from __future__ import unicode_literals, division, absolute_import

import logging

from requests.exceptions import HTTPError

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.imdb import extract_id
from flexget.utils.cached_input import cached
from flexget.entry import Entry
from flexget.utils.soup import get_soup


log = logging.getLogger('imdb_watchlist')
USER_ID_RE = r'^ur\d{7,8}$'
CUSTOM_LIST_RE = r'^ls\d{7,10}$'
USER_LISTS = ['watchlist', 'ratings', 'checkins']
TITLE_TYPE_MAP = {
    'Feature': 'movies',
    'Short Film': 'short films',
    'Documentary': 'documentary',
    'Video Game': 'games',
    'Mini-Series': 'mini series',
    'TV Series': 'shows',
    'TV Episode': 'episodes',
    'TV Movie': 'tv movies',
    'TV Special': 'tv specials',
    'Video': 'videos'
}


class ImdbWatchlist(object):
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
            },
            'force_language':
                {'type': 'string',
                 'default': 'en-us'},
            'type': {
                'oneOf': [
                    one_or_more({'type': 'string', 'enum': list(TITLE_TYPE_MAP.values())}, unique_items=True),
                    {'type': 'string', 'enum': ['all']}
                ]}
        },
        'additionalProperties': False,
        'required': ['list'],
        'anyOf': [
            {'required': ['user_id']},
            {'properties': {'list': {'pattern': CUSTOM_LIST_RE}}}
        ],
        'error_anyOf': 'user_id is required if not using a custom list (lsXXXXXXXXX format)'
    }

    def prepare_config(self, config):
        if 'type' not in config:
            config['type'] = ['all']

        if not isinstance(config['type'], list):
            config['type'] = [config['type']]

        return config

    @cached('imdb_watchlist', persist='2 hours')
    def on_task_input(self, task, config):
        config = self.prepare_config(config)

        # Create movie entries by parsing imdb list page(s) html using beautifulsoup
        log.verbose('Retrieving imdb list: %s', config['list'])

        params = {'view': 'compact', 'start': 1}
        if config['list'] in ['watchlist', 'ratings', 'checkins']:
            url = 'http://www.imdb.com/user/%s/%s' % (config['user_id'], config['list'])
        else:
            url = 'http://www.imdb.com/list/%s' % config['list']

        headers = {'Accept-Language': config.get('force_language')}
        log.debug('Requesting: %s %s', url, headers)

        try:
            page = task.requests.get(url, params=params, headers=headers)
        except HTTPError as e:
            raise plugin.PluginError(e.args[0])
        if page.status_code != 200:
            raise plugin.PluginError('Unable to get imdb list. Either list is private or does not exist.')

        soup = get_soup(page.text)

        try:
            total_item_count = int(soup.find('div', class_='desc').get('data-size'))
            log.verbose('imdb list contains %s items', total_item_count)
        except AttributeError:
            total_item_count = 0
        except ValueError as e:
            # TODO Something is wrong if we get a ValueError, I think
            raise plugin.PluginError('Received invalid movie count: %s - %s' %
                                     (soup.find('div', class_='desc').get('data-size'), e))

        if total_item_count == 0:
            log.verbose('No movies were found in imdb list: %s', config['list'])
            return

        entries = []
        items_processed = 0
        while items_processed < total_item_count:
            # Fetch the next page unless we've just begun
            if items_processed:
                params['start'] = items_processed + 1
                page = task.requests.get(url, params=params)
                if page.status_code != 200:
                    raise plugin.PluginError('Unable to get imdb list.')
                soup = get_soup(page.text)

            items = soup.find_all(attrs={'data-item-id': True, 'class': 'list_item'})

            for item in items:
                items_processed += 1
                a = item.find('td', class_='title').find('a')
                if not a:
                    log.debug('no title link found for row, skipping')
                    continue

                title_type = item.find('td', class_='title_type').text.strip()
                if 'all' not in config['type'] and TITLE_TYPE_MAP.get(title_type) not in config['type']:
                    log.verbose('Skipping title %s since it is a %s', a.text,
                                TITLE_TYPE_MAP.get(title_type).rstrip('s'))
                    continue
                link = ('http://www.imdb.com' + a.get('href')).rstrip('/')
                entry = Entry()
                entry['title'] = a.text
                entry['imdb_type'] = title_type
                try:
                    year = int(item.find('td', class_='year').text)
                    entry['title'] += ' (%s)' % year
                    entry['imdb_year'] = year
                except ValueError:
                    pass
                entry['url'] = link
                entry['imdb_id'] = extract_id(link)
                entry['imdb_name'] = entry['title']
                entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(ImdbWatchlist, 'imdb_watchlist', api_ver=2)
