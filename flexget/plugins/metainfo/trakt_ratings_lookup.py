from __future__ import unicode_literals, division, absolute_import
import hashlib
import logging

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import json

log = logging.getLogger('trakt_ratings')


class TraktWatched(object):
    """
    Query trakt.tv for series and/or movies rated by the user. Set the fields 
    trakt_rating (love|hate) and trakt_rating_advanced (1..10) if the user has
    actually rated the movie/show on trakt. Uses several fields from metainfo 
    plugins (series_name, tvdb_id or imdb_id for series, title, tmdb_id or 
    imdb_id for movies).
    
    Example::
    
        metainfo_series: yes
        thetvdb_lookup: yes
        trakt_ratings_lookup:
          username: xxx
          password: xxx
          api_key: xxx
    
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'api_key': {'type': 'string'}
        },
        'required': ['username', 'password', 'api_key'],
        'additionalProperties': False
    }

    def get_trakt_data(self, task, config, url, null_data=None):
        log.debug('Opening %s' % url)
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
            log.warning('No data returned from trakt.')
            return null_data
        if 'error' in data:
            check_auth()
            raise plugin.PluginError('Error getting trakt list: %s' % data['error'])
        return data
    
    # Run after metainfo_series and thetvdb_lookup
    @plugin.priority(100)
    def on_task_metainfo(self, task, config):
        if not task.entries:
            return
        series = movies = None
        sernul = movnul = False
        seridx = movidx = {}
        for entry in task.entries:
            info = None
            if entry.get('series_name') and not sernul:
                if not series:
                    url = 'http://api.trakt.tv/user/ratings/shows.json/%s/%s' % \
                        (config['api_key'], config['username'])
                    series = self.get_trakt_data(task, config, url, null_data=[])
                    if not series:
                        log.info('No user ratings found for series on trakt.tv')
                        sernul = True
                        continue
                    for idx, val in enumerate(series):
                        seridx[val['title']] = seridx[int(val['tvdb_id'])] = seridx[val['imdb_id']] = idx
                if 'tvdb_id' in entry and entry['tvdb_id'] in seridx:
                    info = series[seridx[entry['tvdb_id']]]
                elif 'imdb_id' in entry and entry['imdb_id'] in seridx:
                    info = series[seridx[entry['imdb_id']]]
                elif 'series_name' in entry and entry['series_name'] in seridx:
                    info = series[seridx[entry['series_name']]]
            elif not entry.get('series_name') and not movnul:
                if not movies:
                    url = 'http://api.trakt.tv/user/ratings/movies.json/%s/%s' % \
                        (config['api_key'], config['username'])
                    movies = self.get_trakt_data(task, config, url, null_data=[])
                    if not movies:
                        log.info('No user ratings found for movies on trakt.tv')
                        movnul = True
                        continue
                    for idx, val in enumerate(movies):
                        movidx[val['title']] = movidx[int(val['tmdb_id'])] = movidx[val['imdb_id']] = idx
                if 'tmdb_id' in entry and entry['tmdb_id'] in movidx:
                    info = movies[movidx[entry['tmdb_id']]]
                elif 'imdb_id' in entry and entry['imdb_id'] in movidx:
                    info = movies[movidx[entry['imdb_id']]]
                elif entry['title'] in movidx:
                    info = movies[movidx[entry['title']]]
            if info:
                entry['trakt_rating'] = info['rating']
                entry['trakt_rating_advanced'] = info['rating_advanced']


@event('plugin.register')
def register_plugin():
    plugin.register(TraktWatched, 'trakt_ratings_lookup', api_ver=2)
