"""Create a Ombi managed list.
"""
from __future__ import annotations

from collections.abc import MutableSet
from typing import Any, Callable, Literal

from loguru import logger
from requests import HTTPError
from typing_extensions import NotRequired, TypedDict  # for Python <3.11 with (Not)Required

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.requests import RequestException

log = logger.bind(name='ombi_list')


class ApiError(Exception):
    """Exception raised when an API call fails."""

    pass


class Config(TypedDict):
    """The config schema for the Ombi managed list."""

    url: str
    api_key: NotRequired[str]
    username: NotRequired[str]
    password: NotRequired[str]
    type: Literal['shows', 'seasons', 'episodes', 'movies']
    status: Literal['approved', 'available', 'requested', 'denied']
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

        headers: dict[str, str] = params.pop('headers', {})
        data = params.pop('data', None)

        # add auth header
        headers.update(self.auth_header.copy())

        response = requests.request(
            method, url, params=params, headers=headers, raise_status=False, json=data
        )

        result = response.json()

        try:
            response.raise_for_status()
        except HTTPError as e:
            log.debug(e)
            if result.get('errors'):
                log.debug(result.get('title'))
                log.debug(result.get('errors'))

            raise e

        if result.get('isError'):
            log.debug(result)
            raise ApiError(result.get('errorMessage'))

        return result

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
        data: dict[str, Any],
    ) -> None:
        self._request = request
        self.entry_type = entry_type
        self.data = data

    def already_requested(self) -> tuple[bool, str]:
        """Check if an entry in Ombi has already been requested.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating if the entry has already been requested and a string indicating the status of the entry.
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

    def mark_available(self):
        """Mark an entry in Ombi as avaliable."""

        if self.data['available']:
            log.verbose(f"{self.data['title']} already available in Ombi.")
            return

        log.info(f"Marking {self.data['title']} as available in Ombi.")

        api_endpoint = f"api/v1/Request/{self.entry_type}/available"

        data = {"id": self.data["requestId"]}

        headers = self._request.create_json_headers()

        try:
            self._request.post(api_endpoint, data=data, headers=headers)

            log.info(f"{self.data['title']} has been marked available.")
            return
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to mark {self.data['title']} as available in Ombi.")
            log.debug(e)
            return

    def mark_denied(self):
        """Mark an entry in Ombi as denied."""

        if self.data.get('denied'):
            log.verbose(f"{self.data['title']} already denied in Ombi.")
            return

        log.info(f"Marking {self.data['title']} as denied in Ombi.")

        api_endpoint = f"api/v1/Request/{self.entry_type}/deny"

        # In the future, we might want to allow the user to specify a reason.
        data = {"id": self.data["requestId"], "reason": "Denied by Flexget automation."}

        headers = self._request.create_json_headers()

        try:
            self._request.post(api_endpoint, data=data, headers=headers)

            log.info(f"{self.data['title']} has been marked denied.")
            return
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to mark {self.data['title']} as denied in Ombi.")
            log.debug(e)
            return

    def mark_approved(self):
        """Mark an entry in Ombi as approved."""

        if self.data.get('approved'):
            log.verbose(f"{self.data['title']} already approved in Ombi.")
            return

        log.info(f"Marking {self.data['title']} as approved in Ombi.")

        api_endpoint = f"api/v1/Request/{self.entry_type}/approve"

        # In the future, we might want to allow the user to specify a reason.
        data = {"id": self.data["requestId"]}

        headers = self._request.create_json_headers()

        try:
            self._request.post(api_endpoint, data=data, headers=headers)

            log.info(f"{self.data['title']} has been marked approved.")
            return
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to mark {self.data['title']} as approved in Ombi.")
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
                f"Not marking {self.data['title']} as requested in Ombi because it is already {status}."
            )
            return

        log.info(f"Requesting {self.data['title']} in Ombi.")

        api_endpoint = f"api/v1/Request/{self.entry_type}"

        # In Ombi an Items ID is also its theMovieDbId
        data = {"theMovieDbId": self.data["id"]}

        headers = self._request.create_json_headers()

        try:
            response: dict[str, Any] = self._request.post(api_endpoint, data=data, headers=headers)

            self.data['requestId'] = response['requestId']

            log.info(f"{self.data['title']} was requested in Ombi.")
            return
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to mark {self.data['title']} as requested in Ombi.")
            log.verbose(e)
            return

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


# In the future this might need split out into 3 classes (Show, Season, Episode)
# for right now, each OmbiTv entry is supposed to represent a single Show, Season, or Episode
class OmbiTv(OmbiEntry):
    """Manage a TV entry in Ombi."""

    entry_type = 'tv'

    def __init__(
        self, base_url: str, auth: Callable[[], dict[str, str]], data: dict[str, Any]
    ) -> None:
        super().__init__(base_url, auth, self.entry_type, data)

    def mark_requested(self):
        """Mark an entry in Ombi as being requested."""

        if self.data['requested']:
            log.verbose(f"{self.data['title']} already requested in Ombi.")
            return

        log.info(f"Requesting {self.data['title']} in Ombi.")

        api_endpoint = "api/v2/Requests/tv"

        data = {"theMovieDbId": self.data["id"]}

        headers = self._request.create_json_headers()

        # I'm not sure what this will even request... If the current entry is a show will it request the whole show?
        # If its a season will it request the whole season? If its an episode will it request only the episode?
        # Here is an example payload from the Ombi API docs. Note even TV shows use tmdb_id instead of tvdb_id
        # {
        #     "theMovieDbId": 0,
        #     "languageCode": "string",
        #     "source": 0,
        #     "requestAll": true,
        #     "latestSeason": true,
        #     "languageProfile": 0,
        #     "firstSeason": true,
        #     "seasons": [
        #         {
        #         "seasonNumber": 0,
        #         "episodes": [
        #             {
        #             "episodeNumber": 0
        #             }
        #         ]
        #         }
        #     ],
        #     "requestOnBehalf": "string",
        #     "rootFolderOverride": 0,
        #     "qualityPathOverride": 0
        # }

        try:
            response: dict[str, Any] = self._request.post(api_endpoint, data=data, headers=headers)

            self.data['requestId'] = response['requestId']

            log.info(f"{self.data['title']} was requested in Ombi.")
            return
        except (HTTPError, ApiError) as e:
            log.error(f"Failed to mark {self.data['title']} as requested in Ombi.")
            log.verbose(e)
            return

    @classmethod
    def from_tvdb_id(cls, base_url: str, tmdb_id: str, auth: Callable[[], dict[str, str]]):
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
            'status': {
                'type': 'string',
                'enum': ['approved', 'available', 'requested', 'denied'],
                'default': 'requested',
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

        log.info(f"Removing {entry['title']} from ombi_list.")

        log.debug(f"Getting OMBI entry for {entry['title']}.")

        ombi_entry = self._get_ombi_entry(entry)

        if not ombi_entry:
            log.error(f"Failed to find OMBI entry for {entry['title']}.")
            return

        ombi_entry.mark_requested()
        ombi_entry.mark_available()

        log.info(f"{entry['title']} was removed from ombi_list.")

        self.invalidate_cache()

    def __isub__(self, entries: list[Entry]):
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

        type = self.config['type']

        if type == 'shows':
            shows = [self.generate_tv_entry(show) for show in requested_items]
            # Shows dont have approvals or available flags so include them all
            self._items.extend(shows)
            return self._items

        if type == 'movies':
            if self.config['status'] == 'requested':
                movies = [self.generate_movie_entry(movie) for movie in requested_items]
                self._items.extend(movies)
                return self._items

            filtered_items = [
                movie for movie in requested_items if movie.get(self.config['status'])
            ]
            movies = [self.generate_movie_entry(movie) for movie in filtered_items]
            self._items.extend(movies)
            return self._items

        # At this point only seasons and episodes are left

        # This code should be refactored to be more readable
        # but I'm not familiar enough with how flexget and Ombi
        # handle seasons and episodes to do it right now
        for parent_request in requested_items:
            for child_request in parent_request["childRequests"]:
                for season in child_request["seasonRequests"]:
                    # Seasons do not have approvals or available flags so include them all
                    if self.config['type'] == 'seasons':
                        entry = self.generate_tv_entry(parent_request, child_request, season)
                        if entry:
                            self._items.append(entry)
                    else:
                        for episode in season['episodes']:
                            if self.config['status'] == 'requested' or episode.get(
                                self.config['status']
                            ):
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

    def _get_ombi_entry(self, entry: Entry) -> OmbiMovie | OmbiTv | None:
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

    def ombi_auth(self) -> dict[str, str]:
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

    def get_requested_items(self) -> dict[str, Any]:
        """Get a list of all the items that have been requested in Ombi.

        Raises:
            plugin.PluginError: If an error occurs while retrieving the list of items.

        Returns:
            Dict[str, Any]: A dictionary containing all the items that have been requested in Ombi.
        """
        request = OmbiRequest(self.config)

        endpoint = (
            "/api/v2/Requests/movie" if self.config['type'] == 'movies' else "/api/v2/Requests/tv"
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
            tmdb_id=parent_request.get('id'),
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
