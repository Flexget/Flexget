from collections.abc import MutableSet
from urllib.parse import urlparse

import requests
from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='couchpotato_list')


class CouchPotatoBase:
    @staticmethod
    def movie_list_request(base_url, port, api_key):
        parsedurl = urlparse(base_url)
        logger.debug('Received movie list request')
        return '{}://{}:{}{}/api/{}/movie.list?status=active'.format(
            parsedurl.scheme,
            parsedurl.netloc,
            port,
            parsedurl.path,
            api_key,
        )

    @staticmethod
    def profile_list_request(base_url, port, api_key):
        parsedurl = urlparse(base_url)
        logger.debug('Received profile list request')
        return '{}://{}:{}{}/api/{}/profile.list'.format(
            parsedurl.scheme,
            parsedurl.netloc,
            port,
            parsedurl.path,
            api_key,
        )

    @staticmethod
    def movie_add_request(base_url, port, api_key):
        parsedurl = urlparse(base_url)
        logger.debug('Received movie add request')
        return '{}://{}:{}{}/api/{}/movie.add'.format(
            parsedurl.scheme,
            parsedurl.netloc,
            port,
            parsedurl.path,
            api_key,
        )

    @staticmethod
    def movie_delete_request(base_url, port, api_key):
        parsedurl = urlparse(base_url)
        logger.debug('Received movie delete request')
        return '{}://{}:{}{}/api/{}/movie.delete?delete_from=wanted'.format(
            parsedurl.scheme,
            parsedurl.netloc,
            port,
            parsedurl.path,
            api_key,
        )

    @staticmethod
    def build_url(base_url, request_type, port, api_key):
        if request_type == 'active':
            return CouchPotatoBase.movie_list_request(base_url, port, api_key)
        elif request_type == 'profiles':
            return CouchPotatoBase.profile_list_request(base_url, port, api_key)
        elif request_type == 'add':
            return CouchPotatoBase.movie_add_request(base_url, port, api_key)
        elif request_type == 'delete':
            return CouchPotatoBase.movie_delete_request(base_url, port, api_key)
        else:
            raise plugin.PluginError('Received unknown API request, aborting.')

    @staticmethod
    def get_json(url):
        try:
            return requests.get(url).json()
        except RequestException as e:
            raise plugin.PluginError(f'Unable to connect to Couchpotato at {url}. Error: {e}')

    @staticmethod
    def quality_requirement_builder(quality_profile):
        """
        Converts CP's quality profile to a format that can be converted to FlexGet QualityRequirement
        """
        # TODO: Not all values have exact matches in flexget, need to update flexget qualities
        sources = {
            'BR-Disk': 'remux',  # Not a perfect match, but as close as currently possible
            'brrip': 'bluray',
            'dvdr': 'dvdrip',  # Not a perfect match, but as close as currently possible
            'dvdrip': 'dvdrip',
            'scr': 'dvdscr',
            'r5': 'r5',
            'tc': 'tc',
            'ts': 'ts',
            'cam': 'cam',
        }

        resolutions = {'1080p': '1080p', '720p': '720p'}

        # Separate strings are needed for each QualityComponent
        # TODO list is converted to set because if a quality has 3d type in CP, it gets duplicated during the conversion
        # TODO when (and if) 3d is supported in flexget this will be needed to removed
        res_string = '|'.join(
            {
                resolutions[quality]
                for quality in quality_profile['qualities']
                if quality in resolutions
            }
        )
        source_string = '|'.join(
            {sources[quality] for quality in quality_profile['qualities'] if quality in sources}
        )

        quality_requirement = (res_string + ' ' + source_string).rstrip()
        logger.debug('quality requirement is {}', quality_requirement)
        return quality_requirement

    @staticmethod
    def list_entries(config, test_mode=None):
        logger.verbose('Connecting to CouchPotato to retrieve movie list.')
        active_movies_url = CouchPotatoBase.build_url(
            config.get('base_url'), 'active', config.get('port'), config.get('api_key')
        )
        active_movies_json = CouchPotatoBase.get_json(active_movies_url)
        # Gets profile and quality lists if include_data is TRUE
        if config.get('include_data'):
            logger.verbose('Connecting to CouchPotato to retrieve profile data.')
            profile_url = CouchPotatoBase.build_url(
                config.get('base_url'), 'profiles', config.get('port'), config.get('api_key')
            )
            profile_json = CouchPotatoBase.get_json(profile_url)

        entries = []
        for movie in active_movies_json['movies']:
            # Related to #1444, corrupt data from CP
            if not all([movie.get('status'), movie.get('title'), movie.get('info')]):
                logger.warning('corrupt movie data received, skipping')
                continue
            quality_req = ''
            logger.debug('movie data: {}', movie)
            if movie['status'] == 'active':
                if config.get('include_data') and profile_json:
                    for profile in profile_json['list']:
                        if (
                            profile['_id'] == movie['profile_id']
                        ):  # Matches movie profile with profile JSON
                            quality_req = CouchPotatoBase.quality_requirement_builder(profile)
                entry = Entry(
                    title=movie["title"],
                    url='',
                    imdb_id=movie['info'].get('imdb'),
                    tmdb_id=movie['info'].get('tmdb_id'),
                    quality_req=quality_req,
                    couchpotato_id=movie.get('_id'),
                )
                if entry.isvalid():
                    logger.debug('returning entry {}', entry)
                    entries.append(entry)
                else:
                    logger.error('Invalid entry created? {}', entry)
                    continue
                # Test mode logging
                if entry and test_mode:
                    logger.info("Test mode. Entry includes:")
                    for key, value in entry.items():
                        logger.info('     {}: {}', key.capitalize(), value)

        return entries

    @staticmethod
    def add_movie(config, entry, test_mode=None):
        if not entry.get('imdb_id'):
            logger.error('Cannot add movie to couchpotato without an imdb ID: {}', entry)
            return
        logger.verbose('Connection to CouchPotato to add a movie to list.')
        add_movie_url = CouchPotatoBase.build_url(
            config.get('base_url'), 'add', config.get('port'), config.get('api_key')
        )
        title = entry.get('movie_name')
        imdb_id = entry.get('imdb_id')
        add_movie_url += f'?title={title}&identifier={imdb_id}'
        add_movie_json = CouchPotatoBase.get_json(add_movie_url)
        return add_movie_json['movie']

    @staticmethod
    def remove_movie(config, movie_id, test_mode=None):
        logger.verbose('Deleting movie from Couchpotato')
        delete_movie_url = CouchPotatoBase.build_url(
            config.get('base_url'), 'delete', config.get('port'), config.get('api_key')
        )
        delete_movie_url += '&id=%s' % movie_id
        CouchPotatoBase.get_json(delete_movie_url)


class CouchPotatoSet(MutableSet):
    supported_ids = ['couchpotato_id', 'imdb_id', 'tmdb_id']
    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string'},
            'port': {'type': 'number', 'default': 80},
            'api_key': {'type': 'string'},
            'include_data': {'type': 'boolean', 'default': False},
        },
        'required': ['api_key', 'base_url'],
        'additionalProperties': False,
    }

    @property
    def movies(self):
        if not self._movies:
            self._movies = CouchPotatoBase.list_entries(self.config)
        return self._movies

    def _find_entry(self, entry):
        for cp_entry in self.movies:
            for sup_id in self.supported_ids:
                if (
                    entry.get(sup_id) is not None
                    and entry[sup_id] == cp_entry[sup_id]
                    or entry.get('title').lower() == cp_entry.get('title').lower()
                ):
                    return cp_entry

    def __init__(self, config):
        self.config = config
        self._movies = None

    def __iter__(self):
        return (entry for entry in self.movies)

    def __len__(self):
        return len(self.movies)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def add(self, entry):
        if not self._find_entry(entry):
            self._movies = None
            movie = CouchPotatoBase.add_movie(self.config, entry)
            logger.verbose(
                'Successfully added movie {} to CouchPotato', movie['info']['original_title']
            )
        else:
            logger.debug('entry {} already exists in couchpotato list', entry)

    def discard(self, entry):
        for movie in self.movies:
            title = entry.get('movie_name') or entry.get('title')
            if movie.get('title').lower() == title.lower():
                movie_id = movie.get('couchpotato_id')
                logger.verbose('Trying to remove movie {} from CouchPotato', title)
                CouchPotatoBase.remove_movie(self.config, movie_id)
                self._movies = None

    @property
    def immutable(self):
        return False

    @property
    def online(self):
        """Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return True

    def get(self, entry):
        return self._find_entry(entry)


class CouchPotatoList:
    schema = CouchPotatoSet.schema

    @staticmethod
    def get_list(config):
        return CouchPotatoSet(config)

    def on_task_input(self, task, config):
        return list(CouchPotatoSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(CouchPotatoList, 'couchpotato_list', api_ver=2, interfaces=['task', 'list'])
