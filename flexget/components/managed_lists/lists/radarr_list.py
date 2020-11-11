import json
from collections.abc import MutableSet
from urllib.parse import quote, urlparse

import requests
from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.qualities import Requirements

logger = logger.bind(name='radarr')


class RadarrRequestError(Exception):
    def __init__(self, value, logger=logger, **kwargs):
        super().__init__()
        # Value is expected to be a string
        value = str(value)
        self.value = value
        self.logger = logger
        self.kwargs = kwargs

    def __str__(self):
        return self.value


class RadarrMovieAlreadyExistsError(Exception):
    pass


def spec_exception_from_response_ex(radarr_request_ex):
    error_message = None

    if "error_message" in radarr_request_ex.kwargs:
        error_message = radarr_request_ex.kwargs["error_message"]

    if not error_message:
        return None

    if error_message.lower() == "this movie has already been added":
        return RadarrMovieAlreadyExistsError()


def request_get_json(url, headers):
    """ Makes a GET request and returns the JSON response """
    try:
        response = requests.get(url, headers=headers, timeout=10)  # TODO: HANGS HERE
        if response.status_code == 200:
            return response.json()
        else:
            raise RadarrRequestError(
                "Invalid response received from Radarr: %s" % response.content
            )
    except RequestException as e:
        raise RadarrRequestError("Unable to connect to Radarr at %s. Error: %s" % (url, e))


def request_delete_json(url, headers):
    """ Makes a DELETE request and returns the JSON response """
    try:
        response = requests.delete(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            raise RadarrRequestError(
                "Invalid response received from Radarr: %s" % response.content
            )
    except RequestException as e:
        raise RadarrRequestError("Unable to connect to Radarr at %s. Error: %s" % (url, e))


def request_post_json(url, headers, data):
    """ Makes a POST request and returns the JSON response """
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        if response.status_code == 201:
            return response.json()
        else:
            error_message = None
            try:
                json_response = response.json()
                if len(json_response) > 0 and "errorMessage" in json_response[0]:
                    error_message = json_response[0]["errorMessage"]
            except ValueError:
                # Raised by response.json() if JSON couln't be decoded
                logger.error('Radarr returned non-JSON error result: {}', response.content)

            raise RadarrRequestError(
                "Invalid response received from Radarr: %s" % response.content,
                logger,
                status_code=response.status_code,
                error_message=error_message,
            )

    except RequestException as e:
        raise RadarrRequestError("Unable to connect to Radarr at %s. Error: %s" % (url, e))


def request_put_json(url, headers):
    """ Makes a PUT request and returns the JSON response """
    try:
        response = requests.put(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise RadarrRequestError(
                "Invalid response received from Radarr: %s" % response.content
            )
    except RequestException as e:
        raise RadarrRequestError("Unable to connect to Radarr at %s. Error: %s" % (url, e))


class RadarrAPIService:
    """ Handles all communication with the Radarr REST API """

    def __init__(self, api_key, base_url, port=None):
        self.api_key = api_key
        parsed_base_url = urlparse(base_url)

        if parsed_base_url.port:
            port = int(parsed_base_url.port)

        self.api_url = "%s://%s:%s%s/api/" % (
            parsed_base_url.scheme,
            parsed_base_url.netloc,
            port,
            parsed_base_url.path,
        )

    def get_profiles(self):
        """ Gets all profiles """
        request_url = self.api_url + "profile"
        headers = self._default_headers()
        return request_get_json(request_url, headers)

    def get_tags(self):
        """ Gets all tags """
        request_url = self.api_url + "tag"
        headers = self._default_headers()
        return request_get_json(request_url, headers)

    def add_tag(self, label):
        """ Adds a tag """
        request_url = self.api_url + "tag"
        headers = self._default_headers()
        data = {"label": label}
        return request_post_json(request_url, headers, json.dumps(data))

    def get_movies(self):
        """ Gets all movies """
        request_url = self.api_url + "movie"
        headers = self._default_headers()
        return request_get_json(request_url, headers)

    def get_root_folders(self):
        """ Gets the root folders """
        request_url = self.api_url + "rootfolder"
        headers = self._default_headers()
        return request_get_json(request_url, headers)

    def delete_movie(self, movie_id):
        """ Deletes a movie provided by its id """
        request_url = self.api_url + "movie/" + str(movie_id)
        headers = self._default_headers()
        return request_delete_json(request_url, headers)

    def lookup_by_term(self, term):
        """ Returns all movies that matches the search term """
        term = quote(term)
        request_url = self.api_url + "movie/lookup?term=" + term
        headers = self._default_headers()
        return request_get_json(request_url, headers)

    def lookup_by_imdb(self, imdb_id):
        """ Returns all movies that matches the imdb id """
        # TODO: make regexp check that imdb_id really is an IMDB_ID
        request_url = self.api_url + "movie/lookup/imdb?imdbId=" + imdb_id
        headers = self._default_headers()
        return request_get_json(request_url, headers)

    def lookup_by_tmdb(self, tmdb_id):
        """ Returns all movies that matches the tmdb id """
        tmdb_id = int(tmdb_id)
        request_url = self.api_url + "movie/lookup/tmdb?tmdbId=" + str(tmdb_id)
        headers = self._default_headers()
        return request_get_json(request_url, headers)

    def add_movie(
        self,
        title,
        year,
        quality_profile_id,
        title_slug,
        images,
        tmdb_id,
        root_folder_path,
        monitored=True,
        add_options=None,
        tags=()
    ):
        """ Adds a movie """
        request_url = self.api_url + "movie"
        headers = self._default_headers()
        data = {
            "title": title,
            "year": year,
            "qualityProfileId": quality_profile_id,
            "titleSlug": title_slug,
            "images": images,
            "tmdbId": tmdb_id,
            "rootFolderPath": root_folder_path,
            "monitored": monitored,
            "tags": tags
        }

        if add_options:
            data["addOptions"] = add_options

        try:
            json_response = request_post_json(request_url, headers, json.dumps(data))
        except RadarrRequestError as ex:
            spec_ex = spec_exception_from_response_ex(ex)
            if spec_ex:
                raise spec_ex
            else:
                raise

        return json_response

    def _default_headers(self):
        """ Returns a dictionary with default headers """
        return {"X-Api-Key": self.api_key}


# Maps (lowercase) Radarr qualities to flexget
# quality reqirement strings
QUALITIES_MAP = {
    "workprint": "workprint",
    "cam": "cam",
    "telesync": "ts",
    "telecine": "tc",
    "dvdscr": "dvdscr",
    "sdtv": "sdtv",
    "dvd": "dvdrip",  # not completely correct
    "dvd-r": "dvdrip",  # not completely correct
    "webdl-480p": "webdl 480p",
    "bluray-480p": "bluray 480p",
    "bluray-576p": "bluray 576p",
    "hdtv-720p": "hdtv 720p",
    "webdl-720p": "webdl 720p",
    "bluray-720p": "bluray 720p",
    "hdtv-1080p": "hdtv 1080p",
    "webdl-1080p": "webdl 1080p",
    "bluray-1080p": "bluray 1080p",
    "remux-1080p": "remux 1080p",
    "hdtv-2160p": "hdtv 2160p",
    "webdl-2160p": "webdl 2160p",
    "bluray-2160p": "bluray 2160p",
    "remux-2160p": "remux 2160p",
    "br-disk": "remux",  # not completely correct
    "raw-hd": "remux",  # not completely correct
    # No idea of how to map these:
    # 'regional': 'UNKNOWN'
}


def radarr_quality_to_flexget_quality_req(radarr_quality):
    """
    Translates the provided Radarr quality string to a Flexget Requirement instance.
    Returns None if translation is unsuccessful
    """

    # QUALITIES_MAP has its keys in lower case
    radarr_quality = radarr_quality.lower()
    if not radarr_quality in QUALITIES_MAP:
        logger.warning(
            "Did not find a suitible translation for Radarr quality '{}'", radarr_quality
        )
        return None

    flexget_quality_req_string = QUALITIES_MAP[radarr_quality]

    try:
        return Requirements(flexget_quality_req_string)
    except ValueError:
        logger.error(
            'Failed to convert {} into a valid quality requirement', flexget_quality_req_string
        )


def get_flexget_qualities(profile, cutoff_only=False):
    quality_requirements = []
    if cutoff_only:
        name = profile["cutoff"]["name"]
        quality_req = radarr_quality_to_flexget_quality_req(name)
        if quality_req:
            quality_requirements.append(quality_req)
    else:
        for quality in profile["items"]:
            if quality["allowed"]:
                name = quality["quality"]["name"]
                quality_req = radarr_quality_to_flexget_quality_req(name)
                if quality_req:
                    quality_requirements.append(quality_req)

    return quality_requirements


class RadarrSet(MutableSet):
    """ Accesses the Radarr movies using the provided the config """

    def __init__(self, config):
        self.config = config
        self.service = RadarrAPIService(config["api_key"], config["base_url"], config["port"])

        # cache tags
        self._tags = None

        # Class member used for caching the items to avoid
        # unnecessary calls to the Radarr API.
        # We use the self.items property to access it.
        # Just set this to None again later to invalidate the cache.
        self._movie_entries = None

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def get_tag_ids(self, entry):
        tags_ids = []

        if not self._tags:
            self._tags = {t["label"].lower(): t["id"] for t in self.service.get_tags()}

        for tag in self.config.get("tags", []):
            if isinstance(tag, int):
                # Handle tags by id
                if tag not in self._tags.values():
                    logger.error('Unable to add tag with id {} to entry {} as the tag does not exist in radarr', entry, tag)
                    continue
                tags_ids.append(tag)
            else:
                # Handle tags by name
                tag = entry.render(tag).lower()
                found = self._tags.get(tag)
                if not found:
                    logger.verbose('Adding missing tag {} to Radarr', tag)
                    found = self.service.add_tag(tag)["id"]
                    self._tags[tag] = found
                tags_ids.append(found)
        return tags_ids

    def discard(self, entry):
        if not entry:
            return

        matching_entry = self._find_matching_entry(entry)
        if matching_entry:
            movie_id = matching_entry["radarr_id"]
            self.service.delete_movie(movie_id)
            logger.verbose('Removed movie {} from Radarr', matching_entry['title'])
            # Clear the cache
            self._movie_entries = None
        else:
            logger.debug('Could not find any matching movie to remove for entry {}', entry)

    def __ior__(self, other):
        for entry in other:
            self.add(entry)

    def __contains__(self, entry):
        if not entry:
            return False

        matching_entry = self._find_matching_entry(entry)

        return matching_entry is not None

    def add(self, entry):
        # The easiest way to add a movie to Radarr is to
        # first use the lookup API. Using that we will get
        # a json response which gives us most of the input
        # we need for the POST request.
        result = self._lookup_movie(entry.get("title"), entry.get("imdb_id"), entry.get("tmdb_id"))

        if result:
            root_folders = self.service.get_root_folders()
            root_folder_path = root_folders[0]["path"]

            try:
                self.service.add_movie(
                    result["title"],
                    result["year"],
                    self.config.get("profile_id"),
                    result["titleSlug"],
                    result["images"],
                    result["tmdbId"],
                    root_folder_path,
                    monitored=self.config.get('monitored', False),
                    tags=self.get_tag_ids(entry)
                )
                logger.verbose('Added movie {} to Radarr list', result['title'])
            except RadarrMovieAlreadyExistsError:
                logger.warning(
                    'Could not add movie {} because it already exists on Radarr', result['title']
                )
            except RadarrRequestError as ex:
                msg = 'The movie add command raised exception: %s' % ex
                logger.error(msg)
                entry.fail(msg)
        else:
            msg = 'The lookup for entry %s did not return any results.Can not add the movie in Radarr.' % entry
            logger.verbose(msg)
            entry.fail(msg)

    def _from_iterable(self, it):
        # The following implementation is what's done in every other
        # list plugin. Does not makes sense.
        # As I understand it, it aims to be an override to base class Set._from_iterable.
        # However, thats a classmethod and this does not even match its signature
        # https://blog.devzero.com/2013/01/28/how-to-override-a-class-method-in-python/
        return set(it)

    def get(self, entry):
        # Here we must return a matching entry using the provided the "hint" entry
        # In Radarr's case we will check different movie ids and then resort to name/year.
        return self._find_matching_entry(entry)

    @property
    def items(self):
        """ Property that returns all items and only loads them all items when needed """
        if self._movie_entries is None:
            self._movie_entries = self._get_movie_entries()
        return self._movie_entries

    @property
    def tags(self):
        """ Property that returns tag by id """
        tags_ids = []
        if self._tags is None:
            existing = {t["label"].lower(): t["id"] for t in self.service.get_tags()}
            for tag in self.config_tags:
                tag = tag.lower()
                found = existing.get(tag)
                if not found:
                    logger.verbose('Adding missing tag {}} to Radarr', tag)
                    found = self.service.add_tag(tag)["id"]
                tags_ids.append(found)
            self._tags = tags_ids
        return self._tags

    @property
    def immutable(self):
        # Here we return True if it's not possible to modify the list.
        # Could depends on the configuration (self.config).
        # But as long it's only about movies it should be alright
        # for Radarr
        return False

    @property
    def online(self):
        # Radarr is an online service, so yes...
        return True

    def _find_matching_entry(self, entry):
        """
        Finds a movie by first checking against the ids of the
        provided entry, and if none matches, check by title name

        :returns entry or None
        """
        for movie_entry in self.items:
            # First check if any of the id attributes match
            for id_attribute in ["tmdb_id", "imdb_id", "radarr_id"]:
                if id_attribute in entry and id_attribute in movie_entry:
                    if entry[id_attribute] == movie_entry[id_attribute]:
                        # Perfect match!
                        return movie_entry

            # Then we check if the title matches
            movie_name = entry.get("movie_name")
            movie_year = entry.get("movie_year")
            if movie_name:
                if movie_name.lower() == movie_entry["movie_name"].lower():
                    # The name matches. If we also have a year lets check that as well.
                    if movie_year == movie_entry.get("movie_year", object()):
                        # Movie name and year matches
                        return movie_entry
                    else:
                        # The movie had no year present
                        return movie_entry

            # Last resort is just to compare the title straight off
            title = entry.get("title").lower()
            if title == movie_entry["title"].lower():
                return movie_entry

    def _get_movie_entries(self):
        """
        Returns a collection of Entry instances
        that represents the entries in the Radarr
        movie list

        :returns list of entries
        """
        profiles = self.service.get_profiles()
        movies = self.service.get_movies()

        profile_to_requirement_cache = {}
        entries = []
        for movie in movies:
            if self.config.get("only_monitored") and not movie["monitored"]:
                continue

            quality_requirements = []

            # Check if we should add quality requirement
            if self.config.get("include_data"):
                movie_profile_id = movie["profileId"]
                for profile in profiles:
                    profile_id = profile["id"]
                    if profile_id == movie_profile_id:
                        if profile_id not in profile_to_requirement_cache:
                            profile_to_requirement_cache[profile_id] = get_flexget_qualities(
                                profile, self.config["only_use_cutoff_quality"]
                            )

                        quality_requirements = profile_to_requirement_cache[profile_id]
                        break

            entry = Entry(
                title=movie["title"],
                url="",
                radarr_id=movie["id"],
                movie_name=movie["title"],
                movie_year=movie["year"],
            )

            # There seem to be a bug in the Radarr API because sometimes
            # the imdbId is omitted in the response. So we can't be sure
            # it's there
            if "imdbId" in movie:
                entry["imdb_id"] = movie["imdbId"]

            if "tmdbId" in movie:
                entry["tmdb_id"] = movie["tmdbId"]

            if len(quality_requirements) > 0:
                entry["quality_req"] = [str(quality_req) for quality_req in quality_requirements]

            entries.append(entry)

        return entries

    # TODO: this fails
    def _lookup_movie(self, title=None, imdb_id=None, tmdb_id=None):
        """
        Uses Radarr's API to lookup a movie, prioritizing IMDB/TMDB
        ids and as a last resort search for the title
        """
        # If the entry has a IMDB id, use that for lookup
        if imdb_id:
            try:
                result = self.service.lookup_by_imdb(imdb_id)
                # lookup_by_imdb returns an empty dictionary in case no match is found
                if result:
                    return result
            except RadarrRequestError as ex:
                logger.error('Radarr IMDB lookup failed: {}', ex)

        # If the entry has a TMDB id, use that for lookup
        if tmdb_id:
            try:
                result = self.service.lookup_by_tmdb(tmdb_id)
                # lookup_by_tmdb returns an empty dictionary in case no match is found
                if result:
                    return result
            except RadarrRequestError as ex:
                logger.error('Radarr TMDB lookup failed: {}', ex)

        # Could not lookup by id. Try to use the title.
        # However, we can only accept any results if it's
        # one item, otherwise we don't know which to select.
        if title:
            try:
                results = self.service.lookup_by_term(title)
                if len(results) > 1:
                    logger.debug(
                        "Radarr lookup for '{}' returned {:d} results. Using the first result '{}'.",
                        title,
                        len(results),
                        results[ 0]['title'],
                    )
                    return results[0]
            except RadarrRequestError as ex:
                logger.error('Radarr search term lookup failed: {}', ex)


class RadarrList:
    """ List plugin for Radarr that also works as an input plugin """

    schema = {
        "type": "object",
        "properties": {
            "base_url": {"type": "string"},
            "port": {"type": "number", "default": 80},
            "api_key": {"type": "string"},
            "only_monitored": {"type": "boolean", "default": True},
            "include_data": {"type": "boolean", "default": False},
            "only_use_cutoff_quality": {"type": "boolean", "default": False},
            "monitored": {"type": "boolean", "default": True},
            "profile_id": {"type": "integer", "default": 1},
            "tags": {"type": "array", "items": {'type': ['integer', 'string']}},
        },
        "required": ["api_key", "base_url"],
        "additionalProperties": False,
    }

    @staticmethod
    def get_list(config):
        # Called when used as a list plugin
        return RadarrSet(config)

    def on_task_input(self, task, config):
        # Called when used as an input plugin
        return list(RadarrSet(config))


@event("plugin.register")
def register_plugin():
    plugin.register(RadarrList, "radarr_list", api_ver=2, interfaces=["task", "list"])
