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

class OmbiBase(object):

    @staticmethod
    def generate_title(item, strip):
        if item.get('releaseDate') and not strip:
            return '%s (%s)' % (item.get('title'), item.get('releaseDate')[0:4] )
        else:
            return item.get('title')

    @staticmethod
    def construct_url(config):
        parsedurl = urlparse(config.get('base_url'))
        if config.get('type') in ['movies']:
            log.debug('Received movie list request')
            return '%s://%s:%s%s/api/v1/Request/movie?apikey=%s' % (parsedurl.scheme, parsedurl.netloc, config.get('port'), parsedurl.path, config.get('api_key'))
        elif config.get('type') in ['shows', 'seasons', 'episodes']:
            log.debug('Received TV list request')
            return '%s://%s:%s%s/api/v1/Request/tv?apikey=%s' % (parsedurl.scheme, parsedurl.netloc, config.get('port'), parsedurl.path, config.get('api_key'))
        else:
            raise plugin.PluginError('Error: Unknown list type %s.' % (config.get('type')))

    @staticmethod
    def get_json(url):
        try:
            return requests.get(url).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Ombi at %s. Error: %s' % (url, e))

    @staticmethod
    def generate_entry(config, parent_request, child_request=False, season=False, episode=False):
        log.debug('Generating Entry')
        entry = Entry()
        if config.get('type') == 'movies':
            log.debug('Found movie: %s', parent_request.get('title'))
            entry = Entry(title=OmbiBase.generate_title(parent_request, config.get('type')),
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
        elif config.get('type') == 'shows':
            log.debug('Found Series: %s', parent_request.get('title'))
            entry = Entry(title=OmbiBase.generate_title(parent_request, config.get('strip_year')),
                          url='http://www.imdb.com/title/' + parent_request.get('imdbId') +'/',
                          series_name=OmbiBase.generate_title(parent_request, config.get('strip_year')),
                          tvdb_id=parent_request.get('tvDbId'),
                          imdb_id=parent_request.get('imdbId'),
                          ombi_status=parent_request.get('status'),
                          ombi_request_id=parent_request.get('id'))
        elif config.get('type') == 'seasons':
            log.debug('Season Number: %s', season.get('seasonNumber'))
            tempSeries_id = 'S' + str(season.get('seasonNumber')).zfill(2)
            entry = Entry(title=OmbiBase.generate_title(parent_request, config.get('strip_year')) + ' ' + tempSeries_id,
                          url='http://www.imdb.com/title/' + parent_request.get('imdbId') +'/',
                          series_name=OmbiBase.generate_title(parent_request, config.get('strip_year')),
                          series_season=season.get('seasonNumber'),
                          series_id=tempSeries_id,
                          tvdb_id=parent_request.get('tvDbId'),
                          imdb_id=parent_request.get('imdbId'),
                          ombi_childrequest_id=child_request.get('id'),
                          ombi_season_id=season.get('id'),
                          ombi_status=parent_request.get('status'),
                          ombi_request_id=parent_request.get('id'))
        elif config.get('type') == 'episodes':
            tempSeries_id = 'S' + str(season.get('seasonNumber')).zfill(2) + 'E' + str(episode.get('episodeNumber')).zfill(2)
            entry = Entry(title=OmbiBase.generate_title(parent_request, config.get('strip_year')) + ' ' + tempSeries_id + ' ' + episode['title'],
                          url=episode.get('url'),
                          series_name=OmbiBase.generate_title(parent_request, config.get('strip_year')),
                          series_season=season.get('seasonNumber'),
                          series_episode=episode.get('episodeNumber'),
                          series_id=tempSeries_id,
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
            raise plugin.PluginError('Error: Unknown list type %s.' % (config.get('type')))
            
        if config.get('type') in ['shows','seasons']:
            # shows/seasons do not have approval or available status so return
            return entry
        elif config.get('only_approved') and not entry.get('ombi_approved'):
            log.verbose('Request not approved skipping: %s', entry.get('title'))
            return False
        elif not config.get('include_available') and entry.get('ombi_available'):
            log.verbose('Request already available skipping: %s', entry.get('title'))
            return False
        else:
            return entry    
        
            
    @staticmethod
    def list_requests(config):
        log.debug('Connecting to Ombi to retrieve request list.')
        connection_url = OmbiBase.construct_url(config)
        
        log.debug('URL %s', connection_url)
        json = OmbiBase.get_json(connection_url)
		
        entries = []        

        for parent_request in json:
            if config.get('type') in ['movies','shows']:
                entry = OmbiBase.generate_entry(config, parent_request)
                if entry:
                    log.debug('Valid entry %s', entry)
                    entries.append(entry)
            else:
                for child_request in parent_request["childRequests"]:
                    for season in child_request["seasonRequests"]:
                        if config.get('type') == 'seasons':
                            entry = OmbiBase.generate_entry(config, parent_request, child_request, season)
                            if entry:
                                log.debug('Valid entry %s', entry)
                                entries.append(entry)
                        else:
                            for episode in season['episodes']:
                                entry = OmbiBase.generate_entry(config, parent_request, child_request, season, episode)
                                if entry:
                                    log.debug('Valid entry %s', entry)
                                    entries.append(entry)
        return entries
 
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
            'strip_year': {'type': 'boolean', 'default': False}
        },
        'required': ['api_key', 'base_url', 'type'],
        'additionalProperties': False
    }

    @property
    def requests(self):
        if not self._requests:
            self._requests = OmbiBase.list_requests(self.config)
        return self._requests
        
    def show_match(self, entry1, entry2):
        if any(entry1.get(ident) is not None and entry1[ident] == entry2.get(ident) for ident in
               ['series_name', 'tvdb_id', 'imdb_id']):
            return True
        return False

    def season_match(self, entry1, entry2):
        return (self.show_match(entry1, entry2) and entry1.get('series_season') is not None and
                entry1['series_season'] == entry2.get('series_season'))

    def episode_match(self, entry1, entry2):
        return (self.season_match(entry1, entry2) and entry1.get('series_episode') is not None and
                entry1['series_episode'] == entry2.get('series_episode'))

    def movie_match(self, entry1, entry2):
        if any(entry1.get(id) is not None and entry1[id] == entry2[id] for id in
               ['imdb_id', 'tmdb_id']):
            return True
        if entry1.get('movie_name') and ((entry1.get('movie_name'), entry1.get('movie_year')) == (entry2.get('movie_name'), entry2.get('movie_year'))):
            return True
        return False

    def _find_entry(self, entry):
        for item in self.requests:
            if self.config['type'] in ['episodes'] and self.episode_match(entry, item):
                return item
            if self.config['type'] in ['shows'] and self.show_match(entry, item):
                return item
            if self.config['type'] in ['movies'] and self.movie_match(entry, item):
                return item

    def __init__(self, config):
        self.config = config
        self._requests = None

    def __iter__(self):
        return (entry for entry in self.requests)

    def __len__(self):
        return len(self.requests)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def add(self, entry):
        log.verbose('List adding not yet implemented')

    def discard(self, entry):
        log.verbose('List item removal not yet implemented')

    @property
    def immutable(self):
        return False

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,like test mode"""
        return True

    def get(self, entry):
        return self._find_entry(entry)

class OmbiList(object):
    schema = OmbiSet.schema
    
    @staticmethod
    def get_list(config):
        return OmbiSet(config)

    def on_task_input(self, task, config):
        return list(OmbiSet(config))

@event('plugin.register')
def register_plugin():
    plugin.register(OmbiList, 'ombi_list', api_ver=2, interfaces=['task', 'list'])
