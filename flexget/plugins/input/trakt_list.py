from __future__ import unicode_literals, division, absolute_import
import hashlib
import logging
import re

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json
from flexget.utils.cached_input import cached

log = logging.getLogger('trakt_list')


def make_list_slug(name):
    """Return the slug for use in url for given list name."""
    slug = name.lower()
    # These characters are just stripped in the url
    for char in '!@#$%^*()[]{}/=?+\\|-_':
        slug = slug.replace(char, '')
    # These characters get replaced
    slug = slug.replace('&', 'and')
    slug = slug.replace(' ', '-')
    return slug


class TraktList(object):
    """Creates an entry for each item in your trakt list.

    Syntax:

    trakt_list:
      username: <value>
      api_key: <value>
      strip_dates: <yes|no>
      movies: <all|loved|hated|collection|watchlist|watched>
      series: <all|loved|hated|collection|watchlist|watched>
      custom: <value>

    Options username and api_key are required.
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'api_key': {'type': 'string'},
            'password': {'type': 'string'},
            'movies': {'enum': ['all', 'loved', 'hated', 'collection', 'watched', 'watchlist']},
            'series': {'enum': ['all', 'loved', 'hated', 'collection', 'watched', 'watchlist']},
            'custom': {'type': 'string'},
            'strip_dates': {'type': 'boolean', 'default': False}
        },
        'required': ['username', 'api_key'],
        'error_oneOf': 'Must specify one and only one of `movies`, `series` or `custom`',
        'oneOf': [
            {'title': 'movie list', 'required': ['movies']},
            {'title': 'series list', 'required': ['series']},
            {'title': 'custom list', 'required': ['custom']}
        ],
        'additionalProperties': False
    }

    movie_map = {
        'title': 'title',
        'url': 'url',
        'imdb_id': 'imdb_id',
        'tmdb_id': 'tmdb_id',
        # Generic fields filled by all movie lookup plugins:
        'movie_name': 'title',
        'movie_year': 'year'}

    series_map = {
        'title': 'title',
        'url': 'url',
        'imdb_id': 'imdb_id',
        'tvdb_id': lambda x: int(x['tvdb_id']),
        'tvrage_id': 'tvrage_id'}

    @cached('trakt_list', persist='2 hours')
    def on_task_input(self, task, config):
        # Don't edit the config, or it won't pass validation on rerun
        url_params = config.copy()
        if 'movies' in config and 'series' in config:
            raise plugin.PluginError('Cannot use both series list and movies list in the same task.')
        if 'movies' in config:
            url_params['data_type'] = 'movies'
            url_params['list_type'] = config['movies']
            map = self.movie_map
        elif 'series' in config:
            url_params['data_type'] = 'shows'
            url_params['list_type'] = config['series']
            map = self.series_map
        elif 'custom' in config:
            url_params['data_type'] = 'custom'
            url_params['list_type'] = make_list_slug(config['custom'])
            # Map type is per item in custom lists
        else:
            raise plugin.PluginError('Must define movie or series lists to retrieve from trakt.')

        url = 'http://api.trakt.tv/user/'
        auth = None
        if url_params['data_type'] == 'custom':
            url += 'list.json/%(api_key)s/%(username)s/%(list_type)s'
        elif url_params['list_type'] == 'watchlist':
            url += 'watchlist/%(data_type)s.json/%(api_key)s/%(username)s'
        else:
            url += 'library/%(data_type)s/%(list_type)s.json/%(api_key)s/%(username)s'
        url = url % url_params

        if 'password' in config:
            auth = {'username': config['username'],
                    'password': hashlib.sha1(config['password']).hexdigest()}

        entries = []
        log.verbose('Retrieving list %s %s...' % (url_params['data_type'], url_params['list_type']))

        try:
            result = task.requests.post(url, data=json.dumps(auth))
        except RequestException as e:
            raise plugin.PluginError('Could not retrieve list from trakt (%s)' % e.args[0])
        try:
            data = result.json()
        except ValueError:
            log.debug('Could not decode json from response: %s', data.text)
            raise plugin.PluginError('Error getting list from trakt.')

        def check_auth():
            if task.requests.post(
                    'http://api.trakt.tv/account/test/' + config['api_key'],
                    data=json.dumps(auth), raise_status=False
            ).status_code != 200:
                raise plugin.PluginError('Authentication to trakt failed.')

        if 'error' in data:
            check_auth()
            raise plugin.PluginError('Error getting trakt list: %s' % data['error'])
        if not data:
            check_auth()
            log.warning('No data returned from trakt.')
            return
        if url_params['data_type'] == 'custom':
            if not isinstance(data['items'], list):
                raise plugin.PluginError('Faulty custom items in response: %s' % data['items'])
            data = data['items']
        for item in data:
            entry = Entry()
            if url_params['data_type'] == 'custom':
                if 'rating' in item:
                    entry['trakt_in_collection'] = item['in_collection']
                    entry['trakt_in_watchlist'] = item['in_watchlist']
                    entry['trakt_rating'] = item['rating']
                    entry['trakt_rating_advanced'] = item['rating_advanced']
                    entry['trakt_watched'] = item['watched']
                if item['type'] == 'movie':
                    map = self.movie_map
                    item = item['movie']
                else:
                    map = self.series_map
                    item = item['show']
            entry.update_using_map(map, item)
            if entry.isvalid():
                if config.get('strip_dates'):
                    # Remove year from end of name if present
                    entry['title'] = re.sub('\s+\(\d{4}\)$', '', entry['title'])
                entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(TraktList, 'trakt_list', api_ver=2)
