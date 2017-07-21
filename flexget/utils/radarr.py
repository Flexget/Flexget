from __future__ import unicode_literals, division, absolute_import
from builtins import *
from future.moves.urllib.parse import urlparse, quote
from future.utils import python_2_unicode_compatible

import logging
import json
import requests
from requests import RequestException

log = logging.getLogger('radarr')


@python_2_unicode_compatible
class RadarrRequestError(Exception):
    def __init__(self, value, logger=log, **kwargs):
        super(RadarrRequestError, self).__init__()
        # Value is expected to be a string
        if not isinstance(value, str):
            value = str(value)
        self.value = value
        self.log = logger
        self.kwargs = kwargs

    def __str__(self):
        return self.value

class RadarrMovieAlreadyExistsError(Exception):
    def __init__(self):
        super(RadarrMovieAlreadyExistsError, self).__init__()

def spec_exception_from_response_ex(radarr_request_ex):

    status_code = None
    error_message = None

    if 'status_code' in radarr_request_ex.kwargs:
        status_code = radarr_request_ex.kwargs['status_code']

    if 'error_message' in radarr_request_ex.kwargs:
        error_message = radarr_request_ex.kwargs['error_message']

    if not error_message:
        return None

    if error_message.lower() == 'this movie has already been added':
        return RadarrMovieAlreadyExistsError()

    return None

def request_get_json(url, headers):
    """ Makes a GET request and returns the JSON response """
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise RadarrRequestError('Invalid response received from Radarr: %s' % response.content)
    except RequestException as e:
        raise RadarrRequestError('Unable to connect to Radarr at %s. Error: %s' % (url, e))

def request_delete_json(url, headers):
    """ Makes a DELETE request and returns the JSON response """
    try:
        response = requests.delete(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise RadarrRequestError('Invalid response received from Radarr: %s' % response.content)
    except RequestException as e:
        raise RadarrRequestError('Unable to connect to Radarr at %s. Error: %s' % (url, e))

def request_post_json(url, headers, data):
    """ Makes a POST request and returns the JSON response """
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 201:
            return response.json()
        else:
            errorMessage = None
            try:
                json_response = response.json()
                if len(json_response) > 0:
                    errorMessage = json_response[0]['errorMessage']
            except:
                # Response wasn't JSON it seems
                pass

            raise RadarrRequestError(
                'Invalid response received from Radarr: %s' % 
                response.content,
                log,
                status_code=response.status_code,
                error_message=errorMessage)

    except RequestException as e:
        raise RadarrRequestError('Unable to connect to Radarr at %s. Error: %s' % (url, e))
def request_put_json(url, headers):
    """ Makes a PUT request and returns the JSON response """
    try:
        response = requests.put(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise RadarrRequestError('Invalid response received from Radarr: %s' % response.content)
    except RequestException as e:
        raise RadarrRequestError('Unable to connect to Radarr at %s. Error: %s' % (url, e))
class RadarrAPIService:
    """ Handles all communication with the Radarr REST API """

    def __init__(self, api_key, base_url, port = None):
        self.api_key = api_key
        parsed_base_url = urlparse(base_url)

        if not parsed_base_url.port is None:
            port = int(parsed_base_url.port)

        self.api_url = '%s://%s:%s%s/api/' % ( 
            parsed_base_url.scheme,
            parsed_base_url.netloc,
            port,
            parsed_base_url.path)
    
    def get_profiles(self):
        """ Gets all profiles """
        request_url = self.api_url + 'profile'
        headers = self.__create_default_headers()
        json_response = request_get_json(request_url, headers)
        return json_response

    def get_movies(self):
        """ Gets all movies """
        request_url = self.api_url + 'movie'
        headers = self.__create_default_headers()
        json_response = request_get_json(request_url, headers)
        return json_response

    def get_rootfolders(self):
        """ Gets the root folders """
        request_url = self.api_url + 'rootfolder'
        headers = self.__create_default_headers()
        json_response = request_get_json(request_url, headers)
        return json_response

    def delete_movie(self, movie_id):
        """ Deletes a movie provided by its id """
        request_url = self.api_url + 'movie/' + str(movie_id)
        headers = self.__create_default_headers()
        json_response = request_delete_json(request_url, headers)
        return json_response

    def lookup_by_term(self, term):
        """ Returns all movies that matches the search term """
        term = quote(term)
        request_url = self.api_url + 'movies/lookup?term=' + term
        headers = self.__create_default_headers()
        json_response = request_get_json(request_url, headers)
        return json_response

    def lookup_by_imdb(self, imdb_id):
        """ Returns all movies that matches the imdb id """
        # TODO: make regexp check that imdb_id really is an IMDB_ID
        request_url = self.api_url + 'movies/lookup/imdb?imdbId=' + imdb_id
        headers = self.__create_default_headers()
        json_response = request_get_json(request_url, headers)
        return json_response

    def lookup_by_tmdb(self, tmdb_id):
        """ Returns all movies that matches the tmdb id """
        tmdb_id = int(tmdb_id)
        request_url = self.api_url + 'movies/lookup/tmdb?tmdbId=' + tmdb_id
        headers = self.__create_default_headers()
        json_response = request_get_json(request_url, headers)
        return json_response
    def add_movie(
            self,
            title, qualityProfileId, titleSlug,
            images, tmdbId, rootFolderPath,
            monitored=True, addOptions=None):
        """ Adds a movie """
        request_url = self.api_url + 'movie'
        headers = self.__create_default_headers()
        data = {}
        data['title'] = title
        data['qualityProfileId'] = qualityProfileId
        data['titleSlug'] = titleSlug
        data['images'] = images
        data['tmdbId'] = tmdbId
        data['rootFolderPath'] = rootFolderPath
        data['monitored'] = monitored
        if addOptions:
            data['addOptions'] = addOptions

        try:
            json_response = request_post_json(request_url, headers, json.dumps(data))
        except RadarrRequestError as ex:
            spec_ex = spec_exception_from_response_ex(ex)
            if spec_ex:
                raise spec_ex
            else:
                raise

        return json_response

    def __create_default_headers(self):
        """ Returns a dictionary with default headers """
        headers = {'X-Api-Key': self.api_key}
        return headers