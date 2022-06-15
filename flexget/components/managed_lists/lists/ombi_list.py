from __future__ import absolute_import, division, unicode_literals

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from collections.abc import MutableSet
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.database import with_session
from flexget.utils.requests import RequestException

log = logger.bind(name='ombi_list')


class OmbiEntry:
    def __init__(self, base_url: str, auth: Callable[[], Dict[str, str]]) -> None:
        self.base_url = base_url
        self.auth = auth

    def _post_data(self, api_endpoint: str, json: Dict[str, Any]) -> Optional[Dict[str, Any]]:

        req_url = f"{self.base_url}/{api_endpoint}"

        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        headers.update(self.auth())
        response = requests.post(req_url, json=json, headers=headers)

        if not response.ok:
            log.error(f"{req_url} return {response.reason}")
            # Do I throw an exception here? Is that allowed from a plugin?
            return None

        return response.json()

    def mark_requested(self):

        if self.data['requested']:
            log.verbose(f"{self.data['title']} already requested in Ombi.")
            return

        log.verbose(f"Requesting {self.data['title']} in Ombi.")

        api_endpoint = (
            "api/v1/Request/movie" if self.entry_type == 'movie' else "api/v2/Requests/tv"
        )

        data = {"theMovieDbId": self.data["theMovieDbId"]}

        response = self._post_data(api_endpoint, data)

        if not response:
            # Unable to mark this item as requested, but what now?
            return

        if response.get('isError'):
            log.error(
                f"Failed to request {self.data['title']} because: {response['errorMessage']}"
            )

        self.data['requestId'] = response['requestId']

        log.verbose(f"{self.data['title']} has been requested.")

    def mark_available(self):

        if self.data['available']:
            log.verbose(f"{self.data['title']} already available in Ombi.")
            return

        log.verbose(f"Marking {self.data['title']} as available in Ombi.")

        api_endpoint = (
            "api/v1/Request/movie/available"
            if self.entry_type == 'movie'
            else "api/v1/Request/tv/available"
        )

        data = {"id": self.data["requestId"]}

        response = self._post_data(api_endpoint, data)

        if not response:
            # Unable to mark this item as requested, but what now?
            return

        if response.get('isError'):
            log.error(
                f"Failed to mark {self.data['title']} as available because: {response['errorMessage']}"
            )

        log.verbose(f"{self.data['title']} has been marked available.")


class OmbiMovie(OmbiEntry):
    entry_type = 'movie'

    def __init__(
        self, base_url: str, auth: Callable[[], Dict[str, str]], data: Dict[str, Any]
    ) -> None:
        super().__init__(base_url, auth)
        self.data = data

    @staticmethod
    def from_imdb_id(base_url: str, tmdb_id: str, auth: Callable[[], Dict[str, str]]):

        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        headers.update(auth())

        url = f"{base_url}/api/v2/Search/{OmbiMovie.entry_type}/{tmdb_id}"

        response = requests.get(url, headers=headers)

        if not response.ok:
            log.error(f"{url} return {response.reason}")
            # Do I throw an exception here? Is that allowed from a plugin?
            return None

        data = response.json()

        # Their is a bug in OMBI where if you get a movie by its TMDB ID
        # then the theMovieDbId field will be blank for some reason...
        data['theMovieDbId'] = tmdb_id

        return OmbiMovie(base_url, auth, data)


class OmbiTv(OmbiEntry):
    entry_type = 'tv'

    def __init__(
        self, base_url: str, auth: Callable[[], Dict[str, str]], data: Dict[str, Any]
    ) -> None:
        super().__init__(base_url, auth)
        self.data = data

    @staticmethod
    def from_tvdb_id(base_url: str, tmdb_id: str, auth: Callable[[], Dict[str, str]]):

        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        headers.update(auth())

        url = f"{base_url}/api/v2/Search/{OmbiTv.entry_type}/moviedb/{tmdb_id}"

        response = requests.get(url, headers=headers)

        if not response.ok:
            log.error(f"{url} return {response.reason}")
            # Do I throw an exception here? Is that allowed from a plugin?
            return None

        data = response.json()

        # Their is a bug in OMBI where if you get a movie by its TMDB ID
        # then the theMovieDbId field will be blank for some reason...
        data['theMovieDbId'] = tmdb_id

        return OmbiTv(base_url, auth, data)


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
            'include_ep_title': {'type': 'boolean', 'default': False},
        },
        'oneOf': [{'required': ['username', 'password']}, {'required': ['api_key']}],
        'required': ['base_url', 'type'],
        'additionalProperties': False,
    }

    @property
    def immutable(self):
        return False

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._items = None
        self._cached_items = None

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def add(self, entry: Entry):

        log.info(f"Adding {entry['title']} to ombi_list.")

        log.debug(f"Getting OMBI entry for {entry['title']}.")

        ombi_entry = self._get_ombi_entry(entry)

        if not ombi_entry:
            log.error(f"Failed to find OMBI entry for {entry['title']}.")
            return

        ombi_entry.mark_requested()

        log.info(f"{entry['title']} was added to ombi_list.")

    def __ior__(self, entries: List[Entry]):

        for entry in entries:
            self.add(entry)

    def discard(self, entry: Entry):
        """Removes an entry from OMBI by marking it as available.

        Args:
            entry (Entry): An item from a task.
        """

        log.info(f"Removing {entry['title']} from ombi_list.")

        log.debug(f"Getting OMBI entry for {entry['title']}.")

        ombi_entry = self._get_ombi_entry(entry)

        if not ombi_entry:
            log.error(f"Failed to find OMBI entry for {entry['title']}.")
            return

        ombi_entry.mark_requested()
        ombi_entry.mark_available()

        log.info(f"{entry['title']} was removed from ombi_list.")

    def __isub__(self, entries: List[Entry]):

        for entry in entries:
            self.discard(entry)

    def _find_entry(self, entry: Entry):

        if "tmdb_id" not in entry:
            log.warning(
                f"{entry['title']} is missing the tmdb_id, consider using tmdb_lookup plugin."
            )

        for item in self.items:
            if item['tmdb_id'] == entry['tmdb_id']:
                return item

        return None

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def clear(self):
        if self.items:
            for item in self.items:
                self.discard(item)
            self._cached_items = None

    def get(self, entry):
        return self._find_entry(entry)

    @property
    def items(self) -> List[Entry]:
        if not self._items:

            json = self.get_request_list()

            self._items = []

            for parent_request in json:
                if self.config.get('type') == 'movies':
                    # check that the request is approved unless user has selected to include everything
                    if (
                        self.config.get('only_approved')
                        and not parent_request.get('approved')
                        or parent_request.get('approved')
                    ):
                        # Always include items that are not available and only include available items if user has selected to do so
                        if (
                            self.config.get('include_available')
                            and parent_request.get('available')
                            or not parent_request.get('available')
                        ):
                            entry = self.generate_movie_entry(parent_request)
                            self._items.append(entry)
                elif self.config.get('type') == 'shows':
                    # Shows do not have approvals or available flags so include them all
                    entry = self.generate_tv_entry(parent_request)
                    self._items.append(entry)
                else:
                    for child_request in parent_request["childRequests"]:
                        for season in child_request["seasonRequests"]:
                            # Seasons do not have approvals or available flags so include them all
                            if self.config.get('type') == 'seasons':
                                entry = self.generate_tv_entry(
                                    parent_request, child_request, season
                                )
                                if entry:
                                    self._items.append(entry)
                            else:
                                for episode in season['episodes']:
                                    # check that the request is approved unless user has selected to include everything
                                    if (
                                        self.config.get('only_approved')
                                        and not episode.get('approved')
                                        or episode.get('approved')
                                    ):
                                        # Always include items that are not available and only include available items if user has selected to do so
                                        if (
                                            self.config.get('include_available')
                                            and episode.get('available')
                                        ) or not episode.get('available'):
                                            entry = self.generate_tv_entry(
                                                parent_request, child_request, season, episode
                                            )
                                            self._items.append(entry)
        return self._items

    @property
    def online(self):
        """Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return True

    # -- Public interface ends here -- #

    def _get_ombi_entry(self, entry: Entry) -> Optional[OmbiEntry]:

        if "tmdb_id" not in entry:
            log.warning(
                f"{entry['title']} is missing the tmdb_id, consider using tmdb_lookup plugin."
            )

        entry_type: str = self.config['type']

        if entry_type == 'movies':
            return OmbiMovie.from_imdb_id(self._get_base_url(), entry['tmdb_id'], self.ombi_auth)

        return OmbiTv.from_tvdb_id(self._get_base_url(), entry['tmdb_id'], self.ombi_auth)

    def generate_series_id(self, season, episode=None):
        tempid = 'S' + str(season.get('seasonNumber')).zfill(2)
        if episode:
            tempid = tempid + 'E' + str(episode.get('episodeNumber')).zfill(2)

        return tempid

    def generate_title(self, item, season=None, episode=None):
        temptitle = item.get('title')

        if item.get('releaseDate') and self.config.get('include_year'):
            temptitle = temptitle + ' (' + str(item.get('releaseDate')[0:4]) + ')'

        if season or episode:
            temptitle = temptitle + ' ' + self.generate_series_id(season, episode)
            if episode:
                if episode.get('title') and self.config.get('include_ep_title'):
                    temptitle = temptitle + ' ' + episode.get('title')

        return temptitle

    def get_access_token(self):
        parsedurl = urlparse(self.config.get('base_url'))
        url = '%s://%s:%s%s/api/v1/Token' % (
            parsedurl.scheme,
            parsedurl.netloc,
            self.config.get('port'),
            parsedurl.path,
        )
        data = {'username': self.config.get('username'), 'password': self.config.get('password')}
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        try:
            access_token = (
                requests.post(url, json=data, headers=headers).json().get('access_token')
            )
            return access_token
        except (RequestException, ValueError) as e:
            raise plugin.PluginError('Ombi username and password login failed: %s' % e)

    def ombi_auth(self) -> Dict[str, str]:
        if self.config.get('api_key'):
            log.debug('Authenticating via api_key')
            api_key = self.config.get('api_key')
            header = {'ApiKey': api_key}
            return header
        elif self.config.get('username') and self.config.get('password'):
            log.debug('Authenticating via username: %s', self.config.get('username'))
            access_token = self.get_access_token()
            return {"Authorization": "Bearer %s" % access_token}
        else:
            raise plugin.PluginError(
                'Error: an api_key or username and password must be configured'
            )

    def _get_base_url(self):
        url = urlparse(self.config.get('base_url'))
        port = self.config.get('port')

        return f"{url.scheme}://{url.netloc}:{port}{url.path}"

    def get_request_list(self):
        auth_header = self.ombi_auth()

        parsedurl = urlparse(self.config.get('base_url'))
        url = ''
        if self.config.get('type') in ['movies']:
            url = '%s://%s:%s%s/api/v1/Request/movie' % (
                parsedurl.scheme,
                parsedurl.netloc,
                self.config.get('port'),
                parsedurl.path,
            )
        elif self.config.get('type') in ['shows', 'seasons', 'episodes']:
            url = '%s://%s:%s%s/api/v1/Request/tv' % (
                parsedurl.scheme,
                parsedurl.netloc,
                self.config.get('port'),
                parsedurl.path,
            )
        else:
            raise plugin.PluginError('Error: Unknown list type %s.' % (self.config.get('type')))
        log.debug('Connecting to Ombi to retrieve request type : %s', self.config.get('type'))
        try:
            return requests.get(url, headers=auth_header).json()
        except (RequestException, ValueError) as e:
            raise plugin.PluginError('Unable to connect to Ombi at %s. Error: %s' % (url, e))

    def generate_movie_entry(self, parent_request):

        log.debug('Found: %s', parent_request.get('title'))

        # If we dont have an imdb id, maybe we should get it from the title?
        if not parent_request.get('imdbId'):
            simdburl = ''
        else:
            simdburl = 'http://www.imdb.com/title/' + parent_request.get('imdbId') + '/'
        return Entry(
            title=self.generate_title(parent_request),
            url=simdburl,
            imdb_id=parent_request.get('imdbId'),
            tmdb_id=parent_request.get('theMovieDbId'),
            movie_name=parent_request.get('title'),
            movie_year=int(parent_request.get('releaseDate')[0:4]),
            ombi_request_id=parent_request.get('id'),
            ombi_released=parent_request.get('released'),
            ombi_status=parent_request.get('status'),
            ombi_approved=parent_request.get('approved'),
            ombi_available=parent_request.get('available'),
            ombi_denied=parent_request.get('denied'),
        )

    def generate_tv_entry(self, parent_request, child_request=None, season=None, episode=None):

        if self.config.get('type') == 'shows':
            log.debug('Found: %s', parent_request.get('title'))
            if not parent_request.get('imdbId'):
                simdburl = ''
            else:
                simdburl = 'http://www.imdb.com/title/' + parent_request.get('imdbId') + '/'
            return Entry(
                title=self.generate_title(parent_request),
                url=simdburl,
                series_name=self.generate_title(parent_request),
                tvdb_id=parent_request.get('tvDbId'),
                imdb_id=parent_request.get('imdbId'),
                ombi_status=parent_request.get('status'),
                ombi_request_id=parent_request.get('id'),
            )
        elif self.config.get('type') == 'seasons':
            log.debug('Found: %s S%s', parent_request.get('title'), season.get('seasonNumber'))
            if not parent_request.get('imdbId'):
                simdburl = ''
            else:
                simdburl = 'http://www.imdb.com/title/' + parent_request.get('imdbId') + '/'
            return Entry(
                title=self.generate_title(parent_request, season),
                url=simdburl,
                series_name=self.generate_title(parent_request),
                series_season=season.get('seasonNumber'),
                series_id=self.generate_series_id(season),
                tvdb_id=parent_request.get('tvDbId'),
                imdb_id=parent_request.get('imdbId'),
                ombi_childrequest_id=child_request.get('id'),
                ombi_season_id=season.get('id'),
                ombi_status=parent_request.get('status'),
                ombi_request_id=parent_request.get('id'),
            )
        elif self.config.get('type') == 'episodes':
            log.debug(
                'Found: %s S%sE%s',
                parent_request.get('title'),
                season.get('seasonNumber'),
                episode.get('episodeNumber'),
            )
            return Entry(
                title=self.generate_title(parent_request, season, episode),
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
                ombi_requested=episode.get('requested'),
            )
        else:
            raise plugin.PluginError('Error: Unknown list type %s.' % (self.config.get('type')))


class OmbiList(object):
    schema = OmbiSet.schema

    def get_list(self, config):
        return OmbiSet(config)

    def on_task_input(self, task, config):
        return list(OmbiSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(OmbiList, 'ombi_list', api_ver=2, interfaces=['task', 'list'])
