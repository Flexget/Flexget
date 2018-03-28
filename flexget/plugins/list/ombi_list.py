from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlparse


import logging
from collections import MutableSet

import requests
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('ombi_list')

class OmbiSet(MutableSet):
    supported_ids = ['imdb_id', 'tmdb_id', 'ombi_id']
    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string'},
            'port': {'type': 'number', 'default': 3579},
            'api_key': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['shows', 'seasons', 'episodes', 'movies']},
            'only_approved': {'type': 'boolean', 'default': True},
            'include_available': {'type': 'boolean', 'default': False},
            'include_year': {'type': 'boolean', 'default': False},
            'include_ep_title': {'type': 'boolean', 'default': False}
        },
        'required': ['base_url', 'type'],
        'oneOf': [
            {'required': ['username', 'password']},
            {'required': ['api_key']}
        ],
        'additionalProperties': False
    }

    @property
    def immutable(self):
        return False

    def __init__(self, config):
        self.config = config
        self._items = None

    def __iter__(self):
        return (item for item in self.items)

    def __len__(self):
        return len(self.items)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def get(self, entry):
        return self._find_entry(entry)

    def generate_series_id(self, season, episode=None):
        tempid = 'S' + str(season.get('seasonNumber')).zfill(2)
        if episode:
            tempid = tempid + 'E' + str(episode.get('episodeNumber')).zfill(2)

        return tempid

    def generate_title(self, item, season=None, episode=None):
        temptitle = item.get('title')

        if item.get('releaseDate') and self.config.get('include_year'):
            temptitle = temptitle + ' (' + str(item.get('releaseDate')[0:4]) +')'

        if season or episode:
            temptitle = temptitle + ' ' + self.generate_series_id(season, episode)
            if episode:
                if episode.get('title') and self.config.get('include_ep_title'):
                    temptitle = temptitle + ' ' + episode.get('title')

        return temptitle

    def get_access_token(self):
        url = self.get_ombi_api_path('Token')
        #parsedurl = urlparse(self.config.get('base_url'))
        #url = '%s://%s:%s%s/api/v1/Token' % (parsedurl.scheme, parsedurl.netloc, self.config.get('port'), parsedurl.path)
        data = {'username': self.config.get('username'),
                'password': self.config.get('password')
        }
        headers = { 'Content-Type': 'application/json',
                    'Accept': 'application/json'
        }
        try:
            log.debug('Logging in with username and password to get access token')
            log.debug('URL %s', url)
            access_token = requests.post(url, json=data, headers=headers).json().get('access_token')
            return access_token
        except RequestException as e:
            raise plugin.PluginError('Ombi username and password login failed: %s' % e)

    def ombi_auth(self):
        if self.config.get('api_key'):
            return {'apikey': self.config.get('api_key')}
        elif self.config.get('username') and self.config.get('password'):
            access_token = self.get_access_token()
            return {"Authorization": "Bearer %s" %access_token}
        else:
            raise plugin.PluginError('Error: an api_key or username and password must be configured')

    def get_request_list(self):
        auth_header = self.ombi_auth()

        if self.config.get('type') in ['movies']:
            url = self.get_ombi_api_path('Request/movie')
        elif self.config.get('type') in ['shows', 'seasons', 'episodes']:
            url = self.get_ombi_api_path('Request/tv')
        else:
            raise plugin.PluginError('Error: Unknown list type %s.' % (self.config.get('type')))
        log.debug('Request URL: %s', url)
        log.debug('Connecting to Ombi to retrieve request list.')
        try:
            return requests.get(url, headers=auth_header).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Ombi at %s. Error: %s' % (url, e))

    def generate_movie_entry(self, parent_request):
        entry = Entry()
        log.debug('Found movie: %s', parent_request.get('title'))
        entry = Entry(title=self.generate_title(parent_request),
                      url='http://www.imdb.com/title/' + parent_request.get('imdbId') +'/',
                      imdb_id=parent_request.get('imdbId'),
                      tmdb_id=parent_request.get('theMovieDbId'),
                      movie_name=parent_request.get('title'),
                      movie_year=int(parent_request.get('releaseDate')[0:4]),
                      ombi_request_id=parent_request.get('id'),
                      ombi_released=parent_request.get('released'),
                      ombi_status=parent_request.get('status'),
                      ombi_approved=parent_request.get('approved'),
                      ombi_available=parent_request.get('available'),
                      ombi_denied=parent_request.get('denied'))
        return entry

    def generate_tv_entry(self, parent_request, child_request=None, season=None, episode=None):
        entry = Entry()
        if self.config.get('type') == 'shows':
            log.debug('Found Series: %s', parent_request.get('title'))
            entry = Entry(title=self.generate_title(parent_request),
                          url='http://www.imdb.com/title/' + parent_request.get('imdbId') +'/',
                          series_name=self.generate_title(parent_request),
                          tvdb_id=parent_request.get('tvDbId'),
                          imdb_id=parent_request.get('imdbId'),
                          ombi_status=parent_request.get('status'),
                          ombi_request_id=parent_request.get('id'))
        elif self.config.get('type') == 'seasons':
            log.debug('Season Number: %s', season.get('seasonNumber'))
            entry = Entry(title=self.generate_title(parent_request, season),
                          url='http://www.imdb.com/title/' + parent_request.get('imdbId') +'/',
                          series_name=self.generate_title(parent_request),
                          series_season=season.get('seasonNumber'),
                          series_id=self.generate_series_id(season),
                          tvdb_id=parent_request.get('tvDbId'),
                          imdb_id=parent_request.get('imdbId'),
                          ombi_childrequest_id=child_request.get('id'),
                          ombi_season_id=season.get('id'),
                          ombi_status=parent_request.get('status'),
                          ombi_request_id=parent_request.get('id'))
        elif self.config.get('type') == 'episodes':
            log.debug('Episode Number: %s', episode.get('episodeNumber'))
            entry = Entry(title=self.generate_title(parent_request, season, episode),
                          url=episode.get('url'),
                          series_name=self.generate_title(parent_request),
                          series_season=season.get('seasonNumber'),
                          series_episode=episode.get('episodeNumber'),
                          series_id=self.generate_series_id(season, episode),
                          tvdb_id=parent_request.get('tvDbId'),
                          imdb_id=parent_request.get('imdbId'),
                          ombi_request_id=parent_request.get('id'),
                          ombi_childrequest_id=child_request.get('id'),
                          ombi_season_id=season.get('id'),
                          ombi_episode_id=episode.get('id'),
                          ombi_approved=episode.get('approved'),
                          ombi_available=episode.get('available'),
                          ombi_requested=episode.get('requested'))
        else:
            raise plugin.PluginError('Error: Unknown list type %s.' % (self.config.get('type')))

        return entry

    def accept_entry(self, entry):
        # check that the request is approved unless user has selected to include everything
        if (self.config.get('only_approved') and not entry.get('approved')) or entry.get('approved'):
            # Always include items that are not available and only include available items if user has selected to do so
            if (self.config.get('include_available') and entry.get('available') or not entry.get('available')):
                return True
            else:
                return False
        else:
            return False

    @property
    def items(self):
        if not self._items:

            json = self.get_request_list()

            self._items = []

            for parent_request in json:
                log.debug('Parent: %s', parent_request)
                if self.config.get('type') == 'movies':
                    # check that the request is approved unless user has selected to include everything
                    if self.accept_entry(parent_request):
                        entry = self.generate_movie_entry(parent_request)
                        log.debug('Entry %s', entry)
                        self._items.append(entry)
                elif self.config.get('type') == 'shows':
                    # Shows do not have approvals or available flags so include them all
                    entry = self.generate_tv_entry(parent_request)
                    log.debug('Valid entry %s', entry)
                    self._items.append(entry)
                else:
                    for child_request in parent_request["childRequests"]:
                        for season in child_request["seasonRequests"]:
                            # Seasons do not have approvals or available flags so include them all
                            if self.config.get('type') == 'seasons':
                                entry = self.generate_tv_entry(parent_request, child_request, season)
                                if entry:
                                    log.debug('Entry %s', entry)
                                    self._items.append(entry)
                            else:
                                for episode in season['episodes']:
                                    if self.accept_entry(parent_request):
                                        entry = self.generate_tv_entry(parent_request, child_request, season, episode)
                                        log.debug('Valid entry %s', entry)
                                        self._items.append(entry)
        return self._items

    def get_ombi_api_path(self, endpoint):
        parsedurl = urlparse(self.config.get('base_url'))
        url = '%s://%s:%s%s/api/v1/%s' % (parsedurl.scheme, parsedurl.netloc, self.config.get('port'), parsedurl.path, endpoint)
        return url

    def add_movie(self, entry):
        log.verbose('Adding entry %s', entry.get('title'))
        auth_header = self.ombi_auth()

        url = self.get_ombi_api_path('Request/movie')
        data = {'theMovieDbId': entry.get('tmdb_id')}
        try:
            return requests.post(url, json=data, headers=auth_header).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Ombi at %s. Error: %s' % (url, e))

    def add(self, entry):
        if self.config.get('type') == 'movies':
            if entry.get('tmdb_id'):
                result = self.add_movie(entry)
                if result.get('message'):
                    log.verbose('%s', result.get('message'))
                elif result.get('errorMessage'):
                    log.verbose('%s', result.get('errorMessage'))
                else:
                    log.verbose('Unknown result')
            else:
                log.verbose('Skipping %s ombi requires an tmdb_id to add movies, try using the tmdb_lookup plugin', entry.get('title'))
        else:
            log.verbose('%s list adding not implemented', self.config.get('type'))

    def find_movie_request_id(self,entry):
        auth_header = self.ombi_auth()
        url = self.get_ombi_api_path('Request/movie/search/') + str(entry.get('movie_name'))
        log.debug('searching for movie request: %s', url)

        try:
            return requests.get(url, headers=auth_header).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Ombi at %s. Error: %s' % (url, e))

    def delete_movie_request_id(self,request_id):
        auth_header = self.ombi_auth()
        url = self.get_ombi_api_path('Request/movie/') + str(request_id)
        log.debug('deleting movie request: %s', url)

        try:
            return requests.delete(url, headers=auth_header)
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Ombi at %s. Error: %s' % (url, e))

    def discard(self, entry):
        search_results = self.find_movie_request_id(entry)
        if search_results:
            for requests in search_results:
                log.debug('Title: %s ID: %s', requests.get('title'), requests.get('id'))
                results = self.delete_movie_request_id(requests.get('id'))
                log.debug('Result: %s', results)
        else:
            log.verbose('Search returned no matching requests.')


    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return True

class OmbiList(object):
    schema = OmbiSet.schema

    def get_list(self, config):
        return OmbiSet(config)

    def on_task_input(self, task, config):
        return list(OmbiSet(config))

@event('plugin.register')
def register_plugin():
    plugin.register(OmbiList, 'ombi_list', api_ver=2, interfaces=['task'])
