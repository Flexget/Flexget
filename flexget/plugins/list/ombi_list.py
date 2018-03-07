from __future__ import unicode_literals, division, absolute_import
from builtins import *
from future.moves.urllib.parse import urlparse

import logging
from collections import MutableSet

import requests
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('ombi_list')

def generate_title(item, strip):
    if item.get('releaseDate') and not strip:
        return '%s (%s)' % (item.get('title'), item.get('releaseDate')[0:4] )
    else:
        return item.get('title')

class OmbiBase(object):
    @staticmethod
    def movie_list_request(base_url, port, api_key):
        parsedurl = urlparse(base_url)
        log.debug('Received movie list request')
        return '%s://%s:%s%s/api/v1/Request/movie?apikey=%s' % (parsedurl.scheme, parsedurl.netloc, port, parsedurl.path, api_key)
    
    @staticmethod    
    def tv_list_request(base_url, port, api_key):
        parsedurl = urlparse(base_url)
        log.debug('Received TV list request')
        return '%s://%s:%s%s/api/v1/Request/tv?apikey=%s' % (parsedurl.scheme, parsedurl.netloc, port, parsedurl.path, api_key)

    @staticmethod
    def get_json(url):
        try:
            return requests.get(url).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Ombi at %s. Error: %s' % (url, e))

    @staticmethod
    def list_requests(config):
        log.debug('Connecting to Ombi to retrieve request list.')
        if config.get('type')  in ['movies']:
            request_url = OmbiBase.movie_list_request(config.get('base_url'), config.get('port'), config.get('api_key'))
        if config.get('type') in ['shows', 'seasons', 'episodes']:
            request_url = OmbiBase.tv_list_request(config.get('base_url'), config.get('port'), config.get('api_key'))
        log.debug('URL %s', request_url)
        json = OmbiBase.get_json(request_url)        
		
        entries = []
        
        if config.get('type') == 'movies':
            for request in json:
                entry = Entry(title=generate_title(request, config.get('type')),
                              url='http://www.imdb.com/title/' + request.get('imdbId') +'/',
                              imdb_id=request.get('imdbId'),
                              tmdb_id=request.get('theMovieDbId'),
                              movie_name=request.get('title'),
                              movie_year=int(request.get('releaseDate')[0:4]),
                              ombi_request_id=request.get('id'),
                              ombi_released=request.get('released'),
                              ombi_status=request.get('status'),
                              ombi_approved=request.get('approved'),
                              ombi_available=request.get('available'),
                              ombi_denied=request.get('denied'))
                if entry.isvalid():
                    log.debug('Valid entry %s', entry)
                    if config.get('only_approved') and not entry.get('ombi_approved'):
                        log.verbose('Request not approved skipping: %s', entry.get('title'))
                    else:
                        if not config.get('include_available') and entry.get('ombi_available'):
                            log.verbose('Request already available skipping: %s', entry.get('title'))
                        else:
                            entries.append(entry)
                else:
                    log.error('Invalid entry created? %s', entry)
                    continue
            return entries
           
        if config.get('type') in ['shows', 'seasons', 'episodes']:
            log.debug('Looking for series')
            for request in json:
                log.debug('Found series: %s', request["title"])
                if config.get('type') == 'shows':
                    entry = Entry(title=generate_title(request, config.get('strip_year')),
                                  url='http://www.imdb.com/title/' + request.get('imdbId') +'/',
                                  series_name=generate_title(request, config.get('strip_year')),
                                  tvdb_id=request.get('tvDbId'),
                                  imdb_id=request.get('imdbId'),
                                  ombi_status=request.get('status'),
                                  ombi_request_id=request.get('id'))
                    if entry.isvalid():
                        log.debug('Valid entry %s', entry)
                        entries.append(entry)
                    else:
                        log.error('Invalid entry created? %s', entry)
                    continue                
                else:
                    for childRequest in request["childRequests"]:
                        log.debug('Child Request ID: %s', childRequest["id"])
                        for season in childRequest["seasonRequests"]:
                            log.debug('Season Number: %s', season["seasonNumber"])
                            if config.get('type') == 'seasons':
                                tempSeries_id = 'S' + str(season["seasonNumber"]).zfill(2)
                                entry = Entry(title=generate_title(request, config.get('strip_year')) + ' ' + tempSeries_id,
                                              url='http://www.imdb.com/title/' + request.get('imdbId') +'/',
                                              series_name=generate_title(request, config.get('strip_year')),
                                              series_season=season["seasonNumber"],
                                              series_id=tempSeries_id,
                                              tvdb_id=request.get('tvDbId'),
                                              imdb_id=request.get('imdbId'),
                                              ombi_childrequest_id=childRequest["id"],
                                              ombi_season_id=season["id"],
                                              ombi_status=request.get('status'),
                                              ombi_request_id=request.get('id'))
                                if entry.isvalid():
                                    log.debug('Valid entry %s', entry)
                                    entries.append(entry)
                                else:
                                    log.error('Invalid entry created? %s', entry)
                                continue
                            else:
                                for episode in season['episodes']:
                                    tempSeries_id = 'S' + str(season["seasonNumber"]).zfill(2) + 'E' + str(episode["episodeNumber"]).zfill(2)
                                    entry = Entry(title=generate_title(request, config.get('strip_year')) + ' ' + tempSeries_id + ' ' + episode['title'],
                                                  url=episode.get('url'),
                                                  series_name=generate_title(request, config.get('strip_year')),
                                                  series_season=season["seasonNumber"],
                                                  series_episode=episode["episodeNumber"],
                                                  series_id=tempSeries_id,
                                                  tvdb_id=request.get('tvDbId'),
                                                  imdb_id=request.get('imdbId'),
                                                  ombi_request_id=request.get('id'),
                                                  ombi_childrequest_id=childRequest["id"],
                                                  ombi_season_id=season["id"],
                                                  ombi_episode_id=episode["id"],
                                                  ombi_approved=episode.get('approved'),
                                                  ombi_available=episode.get('available'),
                                                  ombi_requested=episode.get('requested'))
                                    if entry.isvalid():
                                        log.debug('Valid entry %s', entry)
                                        if config.get('only_approved') and not entry.get('ombi_approved'):
                                            log.verbose('Request not approved skipping: %s', entry.get('title'))
                                        else:
                                            if not config.get('include_available') and entry.get('ombi_available'):
                                                log.verbose('Request already available skipping: %s', entry.get('title'))
                                            else:
                                                entries.append(entry)
                                    else:
                                        log.error('Invalid entry created? %s', entry)
                                        continue
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
