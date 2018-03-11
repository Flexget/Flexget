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
            'type': {'type': 'string', 'enum': ['shows', 'seasons', 'episodes', 'movies']},
            'only_approved': {'type': 'boolean', 'default': True},
            'include_available': {'type': 'boolean', 'default': False},
            'include_year': {'type': 'boolean', 'default': False},
            'include_ep_title': {'type': 'boolean', 'default': False}
        },
        'required': ['api_key', 'base_url', 'type'],
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

    def construct_request_list_url(self):
        parsedurl = urlparse(self.config.get('base_url'))
        if self.config.get('type') in ['movies']:
            log.debug('Received movie list request')
            return '%s://%s:%s%s/api/v1/Request/movie?apikey=%s' % (parsedurl.scheme, parsedurl.netloc, self.config.get('port'), parsedurl.path, self.config.get('api_key'))
        elif self.config.get('type') in ['shows', 'seasons', 'episodes']:
            log.debug('Received TV list request')
            return '%s://%s:%s%s/api/v1/Request/tv?apikey=%s' % (parsedurl.scheme, parsedurl.netloc, self.config.get('port'), parsedurl.path, self.config.get('api_key'))
        else:
            raise plugin.PluginError('Error: Unknown list type %s.' % (self.config.get('type')))

    def get_json(self, url):
        try:
            return requests.get(url).json()
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

    @property
    def items(self):
        if not self._items:
            log.debug('Connecting to Ombi to retrieve request list.')
            connection_url = self.construct_request_list_url()

            log.debug('URL %s', connection_url)
            json = self.get_json(connection_url)

            self._items = []

            for parent_request in json:
                if self.config.get('type') == 'movies':
                    # check that the request is approved unless user has selected to include everything
                    if (self.config.get('only_approved') and not parent_request.get('approved')) or parent_request.get('approved'):
                        # Always include items that are not available and only include available items if user has selected to do so
                        if (self.config.get('include_available') and parent_request.get('available') or not parent_request.get('available')):
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
                                    # check that the request is approved unless user has selected to include everything
                                    if (self.config.get('only_approved') and not episode.get('approved') or episode.get('approved')):
                                        # Always include items that are not available and only include available items if user has selected to do so
                                        if (self.config.get('include_available') and episode.get('available')) or not episode.get('available'):
                                            entry = self.generate_tv_entry(parent_request, child_request, season, episode)
                                            log.debug('Valid entry %s', entry)
                                            self._items.append(entry)
        return self._items

    def add(self, entry):
        log.verbose('List adding not yet implemented')
        return

    def discard(self, entry):
        log.verbose('List item removal not yet implemented')
        return

    def _find_entry(self, entry):
        log.verbose('Find entry not yet implemented')
        return

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
    plugin.register(OmbiList, 'ombi_list', api_ver=2, interfaces=['task', 'list'])
