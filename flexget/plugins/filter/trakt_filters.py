from __future__ import unicode_literals, division, absolute_import
import hashlib
import logging

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import json

log = logging.getLogger('trakt_filter')


class TraktFilter(object):
    """
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'api_key': {'type': 'string'},
            'action': {'enum': ['accept', 'reject'], 'default': 'reject'}
        },
        'required': ['username', 'password', 'api_key'],
        'additionalProperties': False
    }
    
    log = logging.getLogger('trakt_filters')
    
    # Defined by subclasses
    movies = None
    watched = None
    
    def get_trakt_data(self, task, config, url, null_data=None):
        self.log.debug('Opening %s' % url)
        auth = {'username': config['username'],
                'password': hashlib.sha1(config['password']).hexdigest()}
        try:
            data = task.requests.get(url, data=json.dumps(auth)).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to get data from trakt.tv: %s' % e)
        
        def check_auth():
            auth_url = 'http://api.trakt.tv/account/test/' + config['api_key']
            if task.requests.post(auth_url, data=json.dumps(auth), raise_status=False).status_code != 200:
                raise plugin.PluginError('Authentication to trakt failed.')
        
        if not data:
            check_auth()
            self.log.warning('No data returned from trakt.')
            return null_data
        if 'error' in data:
            check_auth()
            raise plugin.PluginError('Error getting trakt list: %s' % data['error'])
        return data
    
    @plugin.priority(-1)
    def on_task_filter(self, task, config):
        entries = task.entries if config['action'] == 'accept' else task.accepted
        if not entries:
            self.log.debug('nothing to do, aborting.')
            return
        data = self.get_trakt_data(task, config, 'http://api.trakt.tv/user/library/%s/%s.json/%s/%s' % 
                                   ('movies' if self.movies else 'shows', 'watched' if self.watched else 'collection', 
                                    config['api_key'], config['username']))
        if data is None:
            self.log.verbose('Nothing found on trakt.tv user profile, aborting.')
            return
        def do_action(entry):
            if config['action'] == 'accept':
                entry.accept('watched' if self.watched else 'collected')
            else:
                entry.reject('watched' if self.watched else 'collected')
        for entry in entries:
            name = entry.get('movie_name', None) if self.movies else entry.get('series_name', None)
            year = entry.get('movie_year', None)
            ssno = entry.get('series_season', None)
            epno = entry.get('series_episode', None)
            imdb = entry.get('imdb_id', None)
            tvdb = entry.get('tvdb_id', None)
            tmdb = entry.get('tmdb_id', None)
            if self.movies and not (name and year and (imdb or tmdb)):
                self.log.debug('Entry `%s` does not look like a movie.' % entry['title'])
                continue
            elif not self.movies and not (name and ssno and epno and (imdb or tvdb)):
                self.log.debug('Entry `%s` does not look like a series episode.' % entry['title'])
                continue
            for item in data:
                if self.movies:
                    if (imdb and imdb == item['imdb_id']) or (tmdb and tmdb == item['tmdb_id']) or \
                        (name.lower() == item['title'].lower() and year == item['year']):
                        do_action(entry)
                        break
                elif (imdb and imdb == item['imdb_id']) or (tvdb and tvdb == item['tvdb_id']):
                    # series matches, check season/episode
                    for season in item['seasons']:
                        if ssno == season['season']:
                            if epno in season['episodes']:
                                do_action(entry)
                            break
                        elif ssno > season['season']:  # seasons are in descending order
                            break
                    break


class TraktSeriesLibrary(TraktFilter):
    movies = False
    watched = False


class TraktSeriesWatched(TraktFilter):
    movies = False
    watched = True


class TraktMoviesLibrary(TraktFilter):
    movies = True
    watched = False


class TraktMoviesWatched(TraktFilter):
    movies = True
    watched = True


@event('plugin.register')
def register_plugin():
    plugin.register(TraktSeriesLibrary, 'trakt_collected_series', api_ver=2)
    plugin.register(TraktMoviesLibrary, 'trakt_collected_movies', api_ver=2)
    plugin.register(TraktSeriesWatched, 'trakt_watched_series', api_ver=2)
    plugin.register(TraktMoviesWatched, 'trakt_watched_movies', api_ver=2)
