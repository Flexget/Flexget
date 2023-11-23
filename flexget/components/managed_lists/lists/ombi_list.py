"""Create a Ombi managed list.
"""

from collections.abc import MutableSet
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from requests import HTTPError

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.requests import RequestException

log = logger.bind(name='ombi_list')


class OmbiRequest:
    def __init__(self, config: Dict[str, str]) -> None:
        self.base_url = config['url']
        # We dont really need the whole config, just the auth part
        # but I'm saving it for now, in case we need to configure
        # token refresh or something
        self.config = config
        self.auth_header = self._create_auth_header()

    def _create_auth_header(self):
        if "api_key" in self.config:
            log.debug('Authenticating via api_key')
            api_key = self.config['api_key']
            header = {'ApiKey': api_key}
            return header

        if self.config.get('username') and self.config.get('password'):
            log.debug('Authenticating via username: %s', self.config.get('username'))
            access_token = self._get_access_token()
            return {"Authorization": "Bearer %s" % access_token}

        raise plugin.PluginError('Error: an api_key or username and password must be configured')

    def _get_access_token(self):
        endpoint = "/api/v1/Token"
        data = {'username': self.config.get('username'), 'password': self.config.get('password')}
        headers = self.create_json_headers()
        try:
            access_token = self._request('post', endpoint, data=data, headers=headers).get(
                'access_token'
            )
            return access_token
        except (HTTPError, RequestException, ValueError) as e:
            raise plugin.PluginError('Ombi username and password login failed') from e

    def _request(self, method, endpoint, **params):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        url = self.base_url + endpoint

        headers: Dict[str, str] = params.pop('headers', {})
        data = params.pop('data', None)

        # add auth header
        headers.update(self.auth_header.copy())

        response = requests.request(
            method, url, params=params, headers=headers, raise_status=False, json=data
        )

        response.raise_for_status()

        return response.json()

    def get(self, endpoint, **params):
        result = self._request('get', endpoint, **params)
        return result

    def post(self, endpoint, **params):
        result = self._request('post', endpoint, **params)
        return result

    def put(self, endpoint, **params):
        result = self._request('put', endpoint, **params)
        return result

    def delete(self, endpoint, **params):
        return self._request('delete', endpoint, **params)

    @classmethod
    def create_json_headers(cls):
        return {'Content-Type': 'application/json', 'Accept': 'application/json'}


class OmbiEntry:
    """Represents a Generic entry returned from the Ombi API."""

    def __init__(
        self,
        request: OmbiRequest,
        entry_type: str,
        data: Dict[str, Any],
    ) -> None:
        self._request = request
        self.entry_type = entry_type
        self.data = data

    def mark_requested(self):
        """Mark an entry in Ombi as being requested."""

        if self.data['requested']:
            log.verbose(f"{self.data['title']} already requested in Ombi.")
            return

        log.verbose(f"Requesting {self.data['title']} in Ombi.")

        api_endpoint = (
            "/api/v1/Request/movie" if self.entry_type == 'movie' else "api/v2/Requests/tv"
        )

        data = {"theMovieDbId": self.data["theMovieDbId"]}

        headers = self._request.create_json_headers()

        try:
            response = self._request.post(api_endpoint, data=data, headers=headers)

            if response.get('isError'):
                log.error(
                    f"Failed to request {self.data['title']} because: {response['errorMessage']}"
                )

            self.data['requestId'] = response['requestId']

            log.verbose(f"{self.data['title']} was requested in Ombi.")
            return
        except HTTPError as e:
            log.error(f"Failed to mark {self.data['title']} as requested in Ombi.")
            log.debug(e)
            return

    def mark_available(self):
        """Mark an entry in Ombi as avaliable."""

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

        headers = self._request.create_json_headers()

        try:
            response = self._request.post(api_endpoint, data=data, headers=headers)

            if response.get('isError'):
                log.error(
                    f"Failed to mark {self.data['title']} as available because: {response['errorMessage']}"
                )

            log.verbose(f"{self.data['title']} has been marked available.")
            return
        except HTTPError as e:
            log.error(f"Failed to mark {self.data['title']} as available in Ombi.")
            log.debug(e)
            return


class OmbiMovie(OmbiEntry):
    """Manage a Movie entry in Ombi."""

    entry_type = 'movie'

    def __init__(self, request: OmbiRequest, data: Dict[str, Any]) -> None:
        super().__init__(request, self.entry_type, data)

    @classmethod
    def from_imdb_id(cls, request: OmbiRequest, imdb_id: str):
        """Create a Ombi Entry from an IMDB ID."""

        headers = request.create_json_headers()

        endpoint = f"api/v2/Search/{cls.entry_type}/imdb/{imdb_id}"

        try:
            data = request.get(endpoint, headers=headers)

            # There is a bug in Ombi where if you get a movie by its imdb_id
            # then the theMovieDbId field will be blank for some reason...

            return OmbiMovie(request, data)
        except HTTPError as e:
            log.error(f"Failed to get OMBI movie by IMDB ID: {imdb_id}")
            log.debug(e)
            return None

    @classmethod
    def from_tmdb_id(cls, request: OmbiRequest, tmdb_id: str):
        """Create a Ombi Entry from an TMDB ID."""

        headers = request

        endpoint = f"/api/v2/Search/{cls.entry_type}/{tmdb_id}"

        try:
            data = request.get(endpoint, headers=headers)

            return OmbiMovie(request, data)
        except HTTPError as e:
            log.error(f"Failed to get OMBI movie by TMDB ID: {tmdb_id}")
            log.debug(e)
            return None

    @classmethod
    def from_id(cls, request: OmbiRequest, entry: Entry):
        """Create a Ombi Entry from an OMBI ID."""

        if entry.get('imdb_id'):
            return cls.from_imdb_id(request, entry['imdb_id'])

        if entry.get('tmdb_id'):
            return cls.from_tmdb_id(request, entry['tmdb_id'])

        raise plugin.PluginError(
            f"Error: Unable to find required ID to lookup OMBI {cls.entry_type}."
        )


# In the future this might need split out into 3 classes (Show, Season, Episode)
class OmbiTv(OmbiEntry):
    """Manage a TV entry in Ombi."""

    entry_type = 'tv'

    def __init__(
        self, base_url: str, auth: Callable[[], Dict[str, str]], data: Dict[str, Any]
    ) -> None:
        super().__init__(base_url, auth, self.entry_type, data)

    @classmethod
    def from_tvdb_id(cls, base_url: str, tmdb_id: str, auth: Callable[[], Dict[str, str]]):
        """Create a Ombi Entry from an TVDB ID."""

        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        headers.update(auth())

        url = f"{base_url}/api/v2/Search/{cls.entry_type}/moviedb/{tmdb_id}"

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
    """The schema for the Ombi managed list."""

    supported_ids = ['imdb_id', 'tmdb_id', 'ombi_id']
    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string'},
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
        'required': ['url', 'type'],
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
        if "imdb_id" not in entry:
            log.warning(
                f"{entry['title']} is missing the imdb_id, consider using tmdb_lookup plugin."
            )
            return None

        for item in self.items:
            if item['imdb_id'] == entry['imdb_id']:
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
        if self._items:
            return self._items

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
                            entry = self.generate_tv_entry(parent_request, child_request, season)
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
        entry_type: str = self.config['type']

        request = OmbiRequest(self.config)

        if entry_type == 'movies':
            return OmbiMovie.from_id(request, entry)

        return OmbiTv.from_tvdb_id(self.config.get('url'), entry['tmdb_id'], self.ombi_auth)

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
        url = f"{self.config.get('url')}/api/v1/Token"
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
        """Returns a dictionary that contains authrization headers for the OMBI API.

        Raises:
            plugin.PluginError: If the api_key or username/password are not defined.

        Returns:
            Dict[str, str]: Authorization headers.
        """

        if "api_key" in self.config:
            log.debug('Authenticating via api_key')
            api_key = self.config['api_key']
            header = {'ApiKey': api_key}
            return header

        if self.config.get('username') and self.config.get('password'):
            log.debug('Authenticating via username: %s', self.config.get('username'))
            access_token = self.get_access_token()
            return {"Authorization": "Bearer %s" % access_token}

        raise plugin.PluginError('Error: an api_key or username and password must be configured')

    def get_request_list(self):
        request = OmbiRequest(self.config)

        if self.config.get('type') in ['movies']:
            endpoint = "/api/v1/Request/movie"
        elif self.config.get('type') in ['shows', 'seasons', 'episodes']:
            endpoint = "/api/v1/Request/tv"
        else:
            raise plugin.PluginError(
                'Error: Unknown OmbiList type %s.' % (self.config.get('type'))
            )

        log.debug('Connecting to Ombi to retrieve list of %s requests.', self.config.get('type'))

        try:
            headers = request.create_json_headers()
            return request.get(endpoint, headers=headers)
        except (HTTPError, RequestException, ValueError) as error:
            raise plugin.PluginError(
                'Error retrieving list of %s requests', self.config.get('type')
            ) from error

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


class OmbiList:
    schema = OmbiSet.schema

    def get_list(self, config):
        return OmbiSet(config)

    def on_task_input(self, task, config):
        return list(OmbiSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(OmbiList, 'ombi_list', api_ver=2, interfaces=['task', 'list'])
