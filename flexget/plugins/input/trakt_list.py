import hashlib
import logging
import urllib2
import re
from flexget.utils import json
from flexget.utils.tools import urlopener
from flexget.utils.cached_input import cached
from flexget.plugin import register_plugin, PluginError
from flexget.entry import Entry

log = logging.getLogger('trakt_list')


class TraktList(object):
    """Creates an entry for each item in your trakt list.

    Syntax:

    trakt_list:
      username: <value>
      api_key: <value>
      strip_dates: <yes|no>
      movies: <all|loved|hated|collection|watchlist>
      series: <all|loved|hated|collection|watchlist|watched>
      custom: <value>

    Options username and api_key are required.
    """

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
        'tvdb_id': 'tvdb_id',
        'tvrage_id': 'tvrage_id'}

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('text', key='username', requried=True)
        root.accept('text', key='api_key', required=True)
        root.accept('text', key='password')
        root.accept('choice', key='movies').accept_choices(['all', 'loved', 'hated', 'collection', 'watchlist'])
        root.accept('choice', key='series').accept_choices(['all', 'loved', 'hated', 'collection', 'watched', 'watchlist'])
        root.accept('text', key='custom')
        root.accept('boolean', key='strip_dates')
        return root

    @cached('trakt_list', persist='2 hours')
    def on_feed_input(self, feed, config):
        if 'movies' in config and 'series' in config:
            raise PluginError('Cannot use both series list and movies list in the same feed.')
        if 'movies' in config:
            config['data_type'] = 'movies'
            config['list_type'] = config['movies']
            map = self.movie_map
        elif 'series' in config:
            config['data_type'] = 'shows'
            config['list_type'] = config['series']
            map = self.series_map
        elif 'custom' in config:
            config['data_type'] = 'custom'
            config['list_type'] = config['custom'].replace(' ', '-')
            # Map type is per item in custom lists
        else:
            raise PluginError('Must define movie or series lists to retrieve from trakt.')

        url = 'http://api.trakt.tv/user/'
        if config['data_type'] == 'custom':
            url += 'list.json/%(api_key)s/%(username)s/%(list_type)s'
        elif config['list_type'] == 'watchlist':
            url += 'watchlist/%(data_type)s.json/%(api_key)s/%(username)s'
        else:
            url += 'library/%(data_type)s/%(list_type)s.json/%(api_key)s/%(username)s'
        url = url % config

        if 'password' in config:
            auth = {'username': config['username'], 'password': hashlib.sha1(config['password']).hexdigest()}
            url = urllib2.Request(url, json.dumps(auth), {'content-type': 'application/json'})

        entries = []
        log.verbose('Retrieving list %s %s...' % (config['data_type'], config['list_type']))
        try:
            data = json.load(urlopener(url, log, retries=2))
        except urllib2.URLError, e:
            raise PluginError('Could not retrieve list from trakt (%s)' % e)
        if 'error' in data:
            raise PluginError('Error getting trakt list: %s' % data['error'])
        if config['data_type'] == 'custom':
            data = data['items']
        for item in data:
            if config['data_type'] == 'custom':
                if item['type'] == 'movie':
                    map = self.movie_map
                    item = item['movie']
                else:
                    map = self.series_map
                    item = item['show']
            entry = Entry()
            entry.update_using_map(map, item)
            if entry.isvalid():
                if config.get('strip_dates'):
                    # Remove year from end of name if present
                    entry['title'] = re.sub('\s+\(\d{4}\)$', '', entry['title'])
                entries.append(entry)

        return entries


register_plugin(TraktList, 'trakt_list', api_ver=2)
