"""Create a Ombi managed list."""

from __future__ import annotations

from collections.abc import MutableSet
from typing import Any, Literal

from loguru import logger
from requests import HTTPError
from typing_extensions import NotRequired, TypedDict  # for Python <3.11 with (Not)Required

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.requests import RequestException

log = logger.bind(name='ombi_list')

# This should probably be a list of enum but the Type hinting is worse than Literal
SUPPORTED_IDS: list[Literal['ombi_id', 'tmdb_id', 'imdb_id']] = ['ombi_id', 'tmdb_id', 'imdb_id']


class ApiError(Exception):
    """Exception raised when an API call fails."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        super().__init__(self.response.get('errorMessage'))


class Config(TypedDict):
    """The config schema for the Ombi managed list."""

    url: str
    api_key: NotRequired[str]
    username: NotRequired[str]
    password: NotRequired[str]
    type: Literal['shows', 'seasons', 'episodes', 'movies']
    status: Literal['approved', 'requested', 'denied', 'all']
    hide_available: bool
    on_remove: NotRequired[Literal['unavailable', 'denied', 'deleted']]
    include_year: bool
    include_ep_title: bool


class OmbiRequest:
    def __init__(self, config: Config) -> None:
        self.base_url = config['url']
        # We dont really need the whole config, just the auth part
        # but I'm saving it for now, in case we need to configure
        # token refresh or something
        self.config: Config = config
        self.auth_header = self._create_auth_header()

    def _create_auth_header(self):
        if "api_key" in self.config:
            log.debug('Authenticating via api_key')
            api_key = self.config['api_key']
            return {'ApiKey': api_key}

        if self.config.get('username') and self.config.get('password'):
            log.debug('Authenticating via username: %s', self.config.get('username'))
            access_token = self._get_access_token()
            return {"Authorization": f"Bearer {access_token}"}

        raise plugin.PluginError('Error: an api_key or username and password must be configured')

    def _get_access_token(self):
        endpoint = "/api/v1/Token"
        data = {'username': self.config.get('username'), 'password': self.config.get('password')}
        headers = self.create_json_headers()
        try:
            return self._request('post', endpoint, data=data, headers=headers).get('access_token')
        except (HTTPError, RequestException, ValueError) as e:
            raise plugin.PluginError('Ombi username and password login failed') from e

    def _request(self, method, endpoint, **params):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        url = self.base_url + endpoint

        headers: dict[str, str] = params.pop('headers', {})
        data = params.pop('data', None)

        # add auth header
        headers.update(self.auth_header.copy())

        response = requests.request(
            method, url, params=params, headers=headers, raise_status=False, json=data
        )

        result = {}

        # I did this instead of a try/catch of the JSONDecodeError,
        # I only had issues with doing a "delete" request
        if 'application/json' in response.headers.get('Content-Type', ''):
            result = response.json()

        try:
            response.raise_for_status()
        except HTTPError as e:
            log.debug(e)
            if result.get('errors'):
                log.debug(result.get('title'))
                log.debug(result.get('errors'))

            raise e

        if isinstance(result, dict) and result.get('isError'):
            log.debug(result)
            raise ApiError(result)

        return result

    def get(self, endpoint, **params):
        return self._request('get', endpoint, **params)

    def post(self, endpoint, **params):
        return self._request('post', endpoint, **params)

    def put(self, endpoint, **params):
        return self._request('put', endpoint, **params)

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
        data: dict[str, Any],
    ) -> None:
        self._request = request
        self.entry_type = entry_type
        self.data = data
        self.ombi_title: str = data['title']

        if data.get('tmdb_season'):
            self.ombi_title = self.ombi_title + ' S' + str(data['tmdb_season']).zfill(2)

        if data.get('tmdb_episode'):
            self.ombi_title = self.ombi_title + ' E' + str(data['tmdb_episode']).zfill(2)

    @property
    def requestId(self) -> str:
        if "requestId" in self.data:
            return self.data['requestId']

        new_data = self._request.get(f"/api/v2/Search/{self.entry_type}/{self.data['id']}")
        self.data = new_data
        return self.data['requestId']

    @requestId.setter
    def requestId(self, value: str):
        self.data['requestId'] = value

    def already_requested(self) -> tuple[bool, str]:
        """Check if an entry in Ombi has already been requested.

        Returns:
            tuple[bool, str]: A tuple containing a boolean indicating if the entry has already been requested and a string indicating the status of the entry.
        """

        if self.data['requested']:
            return True, 'requested'

        if self.data['available']:
            return True, 'available'

        if self.data.get('approved'):
            return True, 'approved'

        if self.data.get('denied'):
            return True, 'denied'

        return False, 'unrequested'

    def mark_requested(self, endpoint: str, data: dict[str, Any]):
        """Mark an entry in Ombi as being requested."""

        log.info(f"Requesting {self.ombi_title} in Ombi.")

        headers = self._request.create_json_headers()

        try:
            response: dict[str, Any] = self._request.post(
                endpoint=endpoint, data=data, headers=headers
            )

            self.requestId = response['requestId']

            log.info(f"{self.ombi_title} was requested in Ombi.")
            return True

        except (HTTPError, ApiError) as error:
            if isinstance(error, ApiError):
                if error.response.get('errrorCode') == 'AlreadyRequested':
                    log.verbose(f"{self.ombi_title} already requested in Ombi.")
                    return True

                error_msg = error.response.get('errorMessage')

                if 'already' in error_msg and 'requested' in error_msg:
                    log.verbose(f"{self.ombi_title} already requested in Ombi.")
                    return True

            log.error(f"Failed to mark {self.ombi_title} as requested in Ombi.")
            log.verbose(error.response)
            return False

    def mark_available(self):
        """Mark an entry in Ombi as avaliable."""

        if self.data['available']:
            log.verbose(f"{self.ombi_title} already available in Ombi.")
            return

        log.info(f"Marking {self.ombi_title} as available in Ombi.")

        api_endpoint = f"api/v1/Request/{self.entry_type}/available"

        data = {"id": self.requestId}

        headers = self._request.create_json_headers()

        try:
            self._request.post(api_endpoint, data=data, headers=headers)

            log.info(f"{self.ombi_title} has been marked available.")
            return
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to mark {self.ombi_title} as available in Ombi.")
            log.debug(e)
            return

    def mark_deleted(self):
        """Mark an entry in Ombi as deleted."""

        if not self.data['requested']:
            log.verbose(f"{self.ombi_title} is not requested in Ombi, unable to delete it.")
            return

        log.info(f"Marking {self.ombi_title} as deleted in Ombi.")

        api_endpoint = f"api/v1/Request/{self.entry_type}/{self.requestId}"

        headers = self._request.create_json_headers()

        try:
            self._request.delete(api_endpoint, headers=headers)

            log.info(f"{self.ombi_title} has been marked deleted.")
            return
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to mark {self.ombi_title} as deleted in Ombi.")
            log.debug(e)
            return

    def mark_unavailable(self):
        """Mark an entry in Ombi as unavaliable."""

        if not self.data['available']:
            log.verbose(f"{self.ombi_title} already unavailable in Ombi.")
            return

        if not self.data['requested']:
            log.verbose(f"{self.ombi_title} is not requested in Ombi, unable to mark unavailable.")
            return

        log.info(f"Marking {self.ombi_title} as unavailable in Ombi.")

        api_endpoint = f"api/v1/Request/{self.entry_type}/unavailable"

        data = {"id": self.requestId}

        headers = self._request.create_json_headers()

        try:
            self._request.post(api_endpoint, data=data, headers=headers)

            log.info(f"{self.ombi_title} has been marked unavailable.")
            return
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to mark {self.ombi_title} as unavailable in Ombi.")
            log.debug(e)
            return

    def mark_denied(self):
        """Mark an entry in Ombi as denied."""

        if self.data.get('denied'):
            log.verbose(f"{self.ombi_title} already denied in Ombi.")
            return

        log.info(f"Marking {self.ombi_title} as denied in Ombi.")

        api_endpoint = f"api/v1/Request/{self.entry_type}/deny"

        # In the future, we might want to allow the user to specify a reason.
        data = {"id": self.requestId, "reason": "Denied by Flexget automation."}

        headers = self._request.create_json_headers()

        try:
            self._request.put(api_endpoint, data=data, headers=headers)

            log.info(f"{self.ombi_title} has been marked denied.")
            return
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to mark {self.ombi_title} as denied in Ombi.")
            log.debug(e)
            return

    def mark_approved(self):
        """Mark an entry in Ombi as approved."""

        if self.data.get('approved'):
            log.verbose(f"{self.ombi_title} already approved in Ombi.")
            return

        log.info(f"Marking {self.ombi_title} as approved in Ombi.")

        api_endpoint = f"api/v1/Request/{self.entry_type}/approve"

        # In the future, we might want to allow the user to specify a reason.
        data = {"id": self.requestId}

        headers = self._request.create_json_headers()

        try:
            self._request.post(api_endpoint, data=data, headers=headers)

            log.info(f"{self.ombi_title} has been marked approved.")
            return
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to mark {self.ombi_title} as approved in Ombi.")
            log.debug(e)
            return


class OmbiMovie(OmbiEntry):
    """Manage a Movie entry in Ombi."""

    entry_type = 'movie'

    def __init__(self, request: OmbiRequest, data: dict[str, Any]) -> None:
        super().__init__(request, self.entry_type, data)

    def mark_requested(self):
        """Mark an entry in Ombi as being requested."""

        # A status such as approved, denied and avaiable are a sub status of requested.
        # Which means you can not mark an entry as approved, denied or available without first marking it as requested.
        # You also can not mark an entry as requested if it is already approved, denied or available.
        already_requested, status = self.already_requested()

        if already_requested:
            log.verbose(
                f"Not marking {self.ombi_title} as requested in Ombi because it is already {status}."
            )
            return True

        api_endpoint = f"api/v1/Request/{self.entry_type}"

        # In Ombi an Items ID is also its theMovieDbId
        data = {"theMovieDbId": self.data["id"]}

        return super().mark_requested(api_endpoint, data)

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
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to get Ombi movie by imdb_id: {imdb_id}")
            log.debug(e)
            return None

    @classmethod
    def from_tmdb_id(cls, request: OmbiRequest, tmdb_id: str):
        """Create a Ombi Entry from an TMDB ID."""

        headers = request.create_json_headers()

        endpoint = f"/api/v2/Search/{cls.entry_type}/{tmdb_id}"

        try:
            data = request.get(endpoint, headers=headers)

            return OmbiMovie(request, data)
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to get Ombi movie by tmdb_id: {tmdb_id}")
            log.debug(e)
            return None

    @classmethod
    def from_id(cls, request: OmbiRequest, entry: Entry):
        """Create a Ombi Entry from an OMBI ID."""

        if entry.get('tmdb_id'):
            return cls.from_tmdb_id(request, entry['tmdb_id'])

        if entry.get('imdb_id'):
            return cls.from_imdb_id(request, entry['imdb_id'])

        raise plugin.PluginError(
            f"Error: Unable to find required ID to lookup Ombi {cls.entry_type}."
        )


class OmbiTv(OmbiEntry):
    """Manage a TV entry in Ombi."""

    entry_type = 'tv'

    def __init__(
        self,
        request: OmbiRequest,
        data: dict[str, Any],
        sub_type: Literal['show', 'season', 'episode'],
    ) -> None:
        super().__init__(request, self.entry_type, data)

        # sub_type can be show, season or episode
        self.sub_type = sub_type

    def mark_requested(self):
        """Mark an entry in Ombi as being requested."""

        api_endpoint = "api/v2/Requests/TV"

        payload = {"theMovieDbId": self.data["id"]}

        if self.sub_type == 'shows':
            payload['requestAll'] = True
        if self.sub_type == 'seasons':
            payload['seasons'] = [
                season
                for season in self.data['seasonRequests']
                if season['seasonNumber'] == self.data['tmdb_season']
            ]
        if self.sub_type == 'episodes':
            payload['seasons'] = [
                {
                    "seasonNumber": self.data['tmdb_season'],
                    "episodes": [{"episodeNumber": self.data['tmdb_episode']}],
                }
            ]

        return super().mark_requested(api_endpoint, payload)

    @classmethod
    def from_tmdb_id(
        cls, request: OmbiRequest, entry: Entry, sub_type: Literal['show', 'season', 'episode']
    ):
        """Create a Ombi Entry from an TVDB ID."""

        headers = request.create_json_headers()

        if not entry.get('tmdb_id'):
            return None

        tmdb_id = entry['tmdb_id']

        endpoint = f"/api/v2/Search/{cls.entry_type}/moviedb/{tmdb_id}"

        try:
            data = request.get(endpoint, headers=headers)

            # need to merge entry and data
            entry.update(data)

            return OmbiTv(request, entry, sub_type)
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to get Ombi movie by tmdb_id: {tmdb_id}")
            log.debug(e)
            return None


class OmbiSet(MutableSet):
    """The schema for the Ombi managed list."""

    supported_ids = SUPPORTED_IDS
    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string'},
            'api_key': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['shows', 'seasons', 'episodes', 'movies']},
            'status': {
                'type': 'string',
                'enum': ['approved', 'requested', 'denied', 'all'],
                'default': 'approved',
            },
            'hide_available': {'type': 'boolean', 'default': True},
            'on_remove': {
                'type': 'string',
                'enum': ['unavailable', 'denied', 'deleted'],
                'default': 'deleted',
            },
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

    def __init__(self, config: dict[str, Any]):
        self.config: Config = config
        self._items: list[Entry] | None = None

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def add(self, entry: Entry):
        log.info(f"Adding {entry['title']} to Ombi as {self.config['status']}.")

        log.debug(f"Getting OMBI entry for {entry['title']}.")

        ombi_entry = self._get_ombi_entry(entry)

        if not ombi_entry:
            log.error(f"Failed to find OMBI entry for {entry['title']}.")
            return

        # To set a status like approved or denied, we need to mark the entry as requested first
        ombi_entry.mark_requested()

        # need to refactor the other mark_${status} methods to
        # call mark_requested() first as its required to be requested first

        # but there is edge cases
        # Not marking Top Gun as requested in Ombi because it is already available.
        # mark_requested  Marking Top Gun as approved in Ombi.
        # mark_requested  {'result': False, 'message': None, 'isError': True, 'errorMessage': 'Request does not exist', 'errorCode': None, 'requestId': 0}
        # mark_requested  Failed to mark Top Gun as approved in Ombi.

        if self.config['status'] == 'requested':
            self.invalidate_cache()
            return

        # Get the correct method, such as mark_approved or mark_denied
        mark_status = getattr(ombi_entry, f"mark_{self.config['status']}", None)

        if not mark_status:
            log.error(
                f"Failed to find correct method to mark {entry['title']} as {self.config['status']}."
            )
            return

        # Mark the entry with the correct status
        mark_status()

        self.invalidate_cache()

    def __ior__(self, entries: list[Entry]):
        for entry in entries:
            self.add(entry)

    def discard(self, entry: Entry):
        """Removes an entry from OMBI by marking it as available.

        Args:
            entry (Entry): An item from a task.
        """

        # I'm wondering if we should be checking if the entry is already
        # in the list of _items first.

        log.info(f"Removing {entry['title']} from ombi_list.")

        log.debug(f"Getting OMBI entry for {entry['title']}.")

        ombi_entry = self._get_ombi_entry(entry)

        if not ombi_entry:
            log.error(f"Failed to find OMBI entry for {entry['title']}.")
            return

        unmark_status = getattr(ombi_entry, f"mark_{self.config['on_remove']}", None)

        if not unmark_status:
            log.error(
                f"Failed to find correct method to mark {entry['title']} as {self.config['on_remove']}."
            )
            return

        unmark_status()

        self.invalidate_cache()

        return

    def __isub__(self, entries: list[Entry]):
        for entry in entries:
            self.discard(entry)

    def _find_entry(self, entry: Entry):
        log.verbose(f"Searching for {entry['title']} in Ombi.")

        find_method = getattr(self, f"_find_{self.config['type']}", None)

        if not find_method:
            raise plugin.PluginError(
                'Error: Unknown list type {}.'.format(self.config.get('type'))
            )

        return find_method(entry)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def invalidate_cache(self):
        self._items = None

    def get(self, entry):
        return self._find_entry(entry)

    @property
    def items(self) -> list[Entry]:
        # If we have already cached the items, return them
        if self._items:
            return self._items

        # Get all the requested items from Ombi
        requested_items = self.get_requested_items()

        # _items can be set to None to invalidate the cache
        self._items = []

        list_type = self.config['type']

        if list_type == 'movies':
            # The Ombi API allows a mix of statuses to be returned,
            # so we have to be careful when we filter them.
            # For example a requested movie can be both approved and denied
            # at the same time.

            filtered_items = filter_ombi_items(requested_items, self.config)

            self._items = [self.generate_movie_entry(item) for item in filtered_items]

            return self._items

        if list_type == 'shows':
            shows = [self.generate_tv_entry(show) for show in requested_items]
            # Shows dont have approvals or available flags so include them all
            self._items = shows
            return self._items

        if list_type == 'seasons':
            seasons = [
                self.generate_tv_entry(show, request, season)
                for show in requested_items
                for request in show['childRequests']
                for season in request['seasonRequests']
            ]
            # Seasons dont have approvals or available flags so include them all
            self._items = seasons
            return self._items

        if list_type == 'episodes':
            # Generate a list of tuples (show, request, season, episode)
            episode_data = [
                (show, request, season, episode)
                for show in requested_items
                for request in show['childRequests']
                for season in request['seasonRequests']
                for episode in season['episodes']
            ]

            # Generate a list of episodes
            episodes = [episode for _, _, _, episode in episode_data]

            # Filter the list of episodes
            filtered_episodes = filter_ombi_items(episodes, self.config)

            # Generate a list of Entry objects
            entries = [
                self.generate_tv_entry(*data)
                for data in episode_data
                if data[3] in filtered_episodes
            ]

            self._items = entries
            return self._items

        # We should never get here, but just in case...
        raise plugin.PluginError('Error: Unknown list type {}.'.format(self.config.get('type')))

    @property
    def online(self):
        """Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return True

    # -- Public interface ends here -- #

    def _find_movies(self, entry: Entry):
        log.debug("Doing a movie search in Ombi.")

        for item in self.items:
            # Search with all the supported ids
            for id in SUPPORTED_IDS:
                if entry.get(id, False) == item.get(id, True):
                    return item

        return None

    def _find_shows(self, entry: Entry):
        log.debug("Doing a show search in Ombi.")

        for item in self.items:
            # Search with all the supported ids
            for id in SUPPORTED_IDS:
                # Since we are searching at the show level,
                # we only need to match the main id
                if entry.get(id, False) == item.get(id, True):
                    return item

        return None

    def _find_seasons(self, entry: Entry):
        log.debug("Doing a season search in Ombi.")

        for item in self.items:
            # Search with all the supported ids
            for id in SUPPORTED_IDS:
                # First find the correct show, then find the correct season
                if entry.get(id, False) == item.get(id, True) and entry.get(
                    'tmdb_season', False
                ) == item.get('tmdb_season', True):
                    return item

        return None

    def _find_episodes(self, entry: Entry):
        log.debug("Doing a episode search in Ombi.")

        for item in self.items:
            # Search with all the supported ids
            for id in SUPPORTED_IDS:
                # First find the correct show, then find the correct season and the correct episode
                if (
                    entry.get(id, False) == item.get(id, True)
                    and entry.get('tmdb_season', False) == item.get('tmdb_season', True)
                    and entry.get('tmdb_episode', False) == item.get('tmdb_episode', True)
                ):
                    return item

        return None

    def _get_ombi_entry(self, entry: Entry) -> OmbiMovie | OmbiTv | None:
        entry_type: str = self.config['type']

        request = OmbiRequest(self.config)

        if entry_type == 'movies':
            return OmbiMovie.from_id(request, entry)

        return OmbiTv.from_tmdb_id(request, entry, entry_type)

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
            if episode and episode.get('title') and self.config.get('include_ep_title'):
                temptitle = temptitle + ' ' + episode.get('title')

        return temptitle

    def get_access_token(self):
        url = f"{self.config.get('url')}/api/v1/Token"
        data = {'username': self.config.get('username'), 'password': self.config.get('password')}
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        try:
            return requests.post(url, json=data, headers=headers).json().get('access_token')
        except (RequestException, ValueError) as e:
            raise plugin.PluginError(f'Ombi username and password login failed: {e}')

    def ombi_auth(self) -> dict[str, str]:
        """Returns a dictionary that contains authrization headers for the OMBI API.

        Raises:
            plugin.PluginError: If the api_key or username/password are not defined.

        Returns:
            dict[str, str]: Authorization headers.
        """

        if "api_key" in self.config:
            log.debug('Authenticating via api_key')
            api_key = self.config['api_key']
            return {'ApiKey': api_key}

        if self.config.get('username') and self.config.get('password'):
            log.debug('Authenticating via username: %s', self.config.get('username'))
            access_token = self.get_access_token()
            return {"Authorization": f"Bearer {access_token}"}

        raise plugin.PluginError('Error: an api_key or username and password must be configured')

    def get_requested_items(self) -> list[OmbiEntry]:
        """Get a list of all the items that have been requested in Ombi.

        Raises:
            plugin.PluginError: If an error occurs while retrieving the list of items.

        Returns:
            dict[str, Any]: A dictionary containing all the items that have been requested in Ombi.
        """
        request = OmbiRequest(self.config)

        endpoint = (
            "/api/v1/Request/movie" if self.config['type'] == 'movies' else "/api/v1/Request/tv"
        )

        log.debug(f"Connecting to Ombi to retrieve list of {self.config['type']} requests.")

        try:
            headers = request.create_json_headers()
            return request.get(endpoint, headers=headers)
        except (HTTPError, ApiError) as error:
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
            ombi_id=parent_request.get('theMovieDbId'),
            movie_name=parent_request.get('title'),
            movie_year=int(parent_request.get('releaseDate')[0:4]),
            ombi_request_id=parent_request.get('id'),
            ombi_released=parent_request.get('released'),
            ombi_status=parent_request.get('requestStatus'),
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
                tmdb_id=parent_request.get('externalProviderId'),
                ombi_id=parent_request.get('externalProviderId'),
                ombi_status=parent_request.get('status'),
                ombi_request_id=parent_request.get('id'),
            )
        if self.config.get('type') == 'seasons':
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
                tmdb_id=parent_request.get('externalProviderId'),
                tmdb_season=season.get('seasonNumber'),
                ombi_id=parent_request.get('externalProviderId'),
                ombi_childrequest_id=child_request.get('id'),
                ombi_season_id=season.get('id'),
                ombi_season=season.get('seasonNumber'),
                ombi_status=parent_request.get('status'),
                ombi_request_id=parent_request.get('id'),
            )
        if self.config.get('type') == 'episodes':
            log.debug(
                'Found: %s S%sE%s',
                parent_request.get('title'),
                season.get('seasonNumber'),
                episode.get('episodeNumber'),
            )
            if not parent_request.get('imdbId'):
                simdburl = ''
            else:
                simdburl = 'http://www.imdb.com/title/' + parent_request.get('imdbId') + '/'
            return Entry(
                title=self.generate_title(parent_request, season, episode),
                url=simdburl,
                series_name=self.generate_title(parent_request),
                series_season=season.get('seasonNumber'),
                series_episode=episode.get('episodeNumber'),
                series_id=self.generate_series_id(season, episode),
                tvdb_id=parent_request.get('tvDbId'),
                imdb_id=parent_request.get('imdbId'),
                tmdb_id=parent_request.get('externalProviderId'),
                tmdb_season=season.get('seasonNumber'),
                tmdb_episode=episode.get('episodeNumber'),
                ombi_id=parent_request.get('externalProviderId'),
                ombi_request_id=parent_request.get('id'),
                ombi_childrequest_id=child_request.get('id'),
                ombi_season_id=season.get('id'),
                ombi_season=season.get('seasonNumber'),
                ombi_episode_id=episode.get('id'),
                ombi_episode=episode.get('episodeNumber'),
                ombi_approved=episode.get('approved'),
                ombi_available=episode.get('available'),
                ombi_requested=episode.get('requested'),
            )
        raise plugin.PluginError('Error: Unknown list type {}.'.format(self.config.get('type')))


class OmbiList:
    schema = OmbiSet.schema

    def get_list(self, config):
        return OmbiSet(config)

    def on_task_input(self, task, config):
        return list(OmbiSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(OmbiList, 'ombi_list', api_ver=2, interfaces=['task', 'list'])


def filter_ombi_items(items: list[dict[str, Any]], config: Config) -> list[dict[str, Any]]:
    """Filter Ombi items based on the config.

    Arguments:
        items {list[dict[str, Any]]} -- The Items returned from the Ombi API.
        config {Config} -- The config for the Ombi managed list.

    Raises:
        plugin.PluginError: If an unknown status is specified in the config.

    Returns:
        list[dict[str, Any]] -- The filtered list of items.
    """

    filtered_items = items

    if config['hide_available']:
        filtered_items = [item for item in filtered_items if not item.get('available')]

    if config['status'] == 'all':
        return filtered_items

    if config['status'] == 'approved':
        return [item for item in filtered_items if item.get('approved') and not item.get('denied')]

    if config['status'] == 'denied':
        return [item for item in filtered_items if item.get('denied')]

    if config['status'] == 'requested':
        return [
            item for item in filtered_items if not item.get('approved') and not item.get('denied')
        ]

    # We shouldn't get here, but just in case...
    raise plugin.PluginError('Error: Unknown status {}.'.format(config.get('status')))
