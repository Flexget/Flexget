from __future__ import unicode_literals, division, absolute_import
from builtins import *

import logging
from collections import MutableSet

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.qualities import Requirements
from flexget.utils.radarr import RadarrAPIService

# Maps (lowercase) Radarr qualities to flexget
# quality reqirement strings
QUALITIES_MAP = {
    'workprint': 'workprint',
    'cam': 'cam',
    'telesync': 'ts',
    'telecine': 'tc',
    'dvdscr': 'dvdscr',
    'sdtv': 'sdtv',
    'dvd': 'dvdrip', # not completely correct
    'dvd-r': 'dvdrip', # not completely correct
    'webdl-480p': 'webdl 480p',
    'bluray-480p': 'bluray 480p',
    'bluray-576p': 'bluray 576p',
    'hdtv-720p': 'hdtv 720p',
    'webdl-720p': 'webdl 720p',
    'bluray-720p': 'bluray 720p',
    'hdtv-1080p': 'hdtv 1080p',
    'webdl-1080p': 'webdl 1080p',
    'bluray-1080p': 'bluray 1080p',
    'remux-1080p': 'remux 1080p',
    'hdtv-2160p': 'hdtv 2160p',
    'webdl-2160p': 'webdl 2160p',
    'bluray-2160p': 'bluray 2160p',
    'remux-2160p': 'remux 2160p',
    'br-disk': 'remux', # not completely correct
    'raw-hd': 'remux', # not completely correct

    # No idea of how to map these:
    # 'regional': 'UNKNOWN'
}

log = logging.getLogger('radarr_list')

def radarr_quality_to_flexget_quality_req(radarr_quality):
    """
    Translates the provided Radarr quality string to a Flexget Requirement instance.
    Returns None if translation is unsuccessful
    """

    # QUALITIES_MAP has its keys in lower case
    radarr_quality = radarr_quality.lower()
    if not radarr_quality in QUALITIES_MAP:
        log.warning('Did not find a suitible translation for Radarr quality \'%s\'',
                    radarr_quality)
        return None

    flexget_quality_req_string = QUALITIES_MAP[radarr_quality]

    try:
        return Requirements(flexget_quality_req_string)
    except ValueError:
        log.error('Failed to convert %s into a valid quality requirement',
                  flexget_quality_req_string)
        return None
def get_flexget_qualities(profile, cutoff_only=False):
    quality_requirements = []
    if cutoff_only:
        name = profile['cutoff']['name']
        quality_req = radarr_quality_to_flexget_quality_req(name)
        if quality_req:
            quality_requirements.append(quality_req)
    else:
        for quality in profile['items']:
            if quality['allowed']:
                name = quality['quality']['name']
                quality_req = radarr_quality_to_flexget_quality_req(name)
                if quality_req:
                    quality_requirements.append(quality_req)

    return quality_requirements



class RadarrSet(MutableSet):
    """ Accesses the Radarr movies using the provided the config """

    def __init__(self, config):
        self.config = config
        self.service = RadarrAPIService(
            config['api_key'],
            config['base_url'],
            config['port']
            )

        # Class member used for caching the items to avoid
        # unnecessary calls to the Radarr API.
        # We use the self.items property to access it.
        # Just set this to None again later to invalidate the cache.
        self._movie_entries = None

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def discard(self, entry):
        if not entry:
            return

        matching_entry = self.__find_matching_entry(entry)
        if matching_entry:
            movie_id = matching_entry['radarr_id']
            response = self.service.delete_movie(movie_id)
            log.verbose('Removed movie %s from Radarr', matching_entry['title'])
            # Clear the cache
            self._movie_entries = None
        else:
            log.debug('Could not find any matching movie to remove for entry %s', entry)

    def __ior__(self, other):
        for entry in other:
            self.add(entry)

    def __contains__(self, entry):
        if not entry:
            return False

        matching_entry = self.__find_matching_entry(entry)

        return matching_entry is not None

    def add(self, entry):

        # The easiest way to add a movie to Radarr is to
        # first use the lookup API. Using that we will get
        # a json response which gives us most of the input
        # we need for the POST request.

        result = self.__lookup_movie(entry.get('title'),
                                     entry.get('imdb_id'),
                                     entry.get('tmdb_id'))

        if result:
            rootFolders = self.service.get_root_folders()
            rootFolderPath = rootFolders[0]['path']

            # TODO: should we let the user affect this one,
            # or try to parse the 'quality' entry somehow?
            qualityProfileId = 1

            try:
                add_result = self.service.add_movie(
                    result['title'],
                    qualityProfileId,
                    result['titleSlug'],
                    result['images'],
                    result['tmdbId'],
                    rootFolderPath)
                log.verbose('Added movie %ls to Radarr list', result['title'])
            except RadarrMovieAlreadyExistsError:
                log.warning('Could not add movie %ls because it already exists on Radarr',
                            result['title'])
            except RadarrRequestError as ex:
                log.error('The movie add command raised exception: %s', ex)
        else:
            log.verbose('The lookup for entry %s did not return any results.'
                        'Can not add the movie in Radarr.',
                        entry)

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
        return self.__find_matching_entry(entry)

    @property
    def items(self):
        """ Property that returns all items and only loads them all items when needed """

        if self._movie_entries is None:
            self._movie_entries = self.__get_movie_entries()
        return self._movie_entries

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

    def __find_matching_entry(self, entry):
        """
        Finds a movie by first checking agains the ids of the provided entry,
        and if none matches, check by title name
        """

        for movie_entry in self.items:

            # First check if any of the id attributes match
            for id_attribute in ['tmdb_id', 'imdb_id', 'radarr_id']:
                if id_attribute in entry and id_attribute in movie_entry:
                    if entry[id_attribute] == movie_entry[id_attribute]:
                        # Perfect match!
                        return movie_entry

            # Then we check if the title matches
            movie_name = entry.get('movie_name')
            movie_year = entry.get('movie_year')
            if movie_name:
                if movie_name.lower() == movie_entry['movie_name'].lower():
                    # The name matches. If we also have a year lets check that as well.
                    if movie_year and movie_entry['movie_year']:
                        if movie_year == movie_entry['movie_year']:
                            # Movie name and year matches
                            return movie_entry
                    else:
                        # The movie had no year present
                        return movie_entry

            # Last resort is just to compare the title straight off
            title = entry.get('title').lower()
            if title == movie_entry['title'].lower():
                return movie_entry

        # Did not find a match
        return None

    def __get_movie_entries(self):
        """
        Returns a collection of Entry instances
        that represents the entries in the Radarr
        movie list
        """
        profiles = self.service.get_profiles()
        movies = self.service.get_movies()

        profile_to_requirement_cache = {}
        entries = []
        for movie in movies:

            if self.config.get('only_monitored') and not movie['monitored']:
                continue

            quality_requirements = []

            # Check if we should add quality requirement
            if self.config.get('include_data'):
                movieProfileId = movie['profileId']
                for profile in profiles:
                    profileId = profile['id']
                    if profileId == movieProfileId:
                        if not profileId in profile_to_requirement_cache:
                            profile_to_requirement_cache[profileId] = get_flexget_qualities(
                                profile,
                                self.config['only_use_cutoff_quality'])

                        quality_requirements = profile_to_requirement_cache[profileId]

                        break


            entry = Entry(
                title=movie['title'],
                url='',
                radarr_id=movie['id'],
                movie_name=movie['title'],
                movie_year=movie['year']
            )

            # There seem to be a bug in the Radarr API because sometimes
            # the imdbId is omitted in the response. So we can't be sure
            # it's there
            if 'imdbId' in movie:
                entry['imdb_id'] = movie['imdbId']

            if 'tmdbId' in movie:
                entry['tmdb_id'] = movie['tmdbId']

            if len(quality_requirements) > 0:
                entry['quality_req'] = [str(quality_req) for quality_req in quality_requirements]

            entries.append(entry)

        return entries

    def __lookup_movie(self, title=None, imdb_id=None, tmdb_id=None):
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
                log.error('The IMDB lookup raised exception: %s', ex)

        # If the entry has a TMDB id, use that for lookup
        if tmdb_id:
            try:
                result = self.service.lookup_by_tmdb(tmdb_id)
                # lookup_by_tmdb returns an empty dictionary in case no match is found
                if result:
                    return result
            except RadarrRequestError as ex:
                log.error('The TMDB lookup raised exception: %s', ex)

        # Could not lookup by id. Try to use the title.
        # However, we can only accept any results if it's
        # one item, otherwise we don't know which to select.
        if title:
            try:
                results = self.service.lookup_by_term(title)
                if len(results) > 1:
                    log.debug(
                        'The lookup for \'%s\' returned %d results. Using the first result \'%s\'.',
                        title,
                        len(results),
                        results[0]['title']
                    )
                    return results[0]
            except RadarrRequestError as ex:
                log.error('The search term lookup raised exception: %s', ex)

        return None

class RadarrList(object):
    """ List plugin for Radarr that also works as an input plugin """

    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string'},
            'port': {'type': 'number', 'default': 80},
            'api_key': {'type': 'string'},
            'only_monitored': {'type': 'boolean', 'default': True},
            'include_data': {'type': 'boolean', 'default': False},
            'only_use_cutoff_quality': {'type': 'boolean', 'default': False}
        },
        'required': ['api_key', 'base_url'],
        'additionalProperties': False
    }

    @staticmethod
    def get_list(config):
        # Called when used as a list plugin
        return RadarrSet(config)

    def on_task_input(self, task, config):
        # Called when used as an input plugin
        return list(RadarrSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(RadarrList, 'radarr_list', api_ver=2, interfaces=['task', 'list'])
