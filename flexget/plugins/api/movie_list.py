from __future__ import unicode_literals, division, absolute_import

import copy
import logging

from flask import jsonify, request

from flexget.api import api, APIResource
from flexget.plugins.api.movie_queue import empty_response
from flexget.plugins.list.movie_list import PluginMovieList as ml

log = logging.getLogger('movie_list')

movie_list_api = api.namespace('movie_list', description='Movie List operations')

default_error_schema = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'}
    }
}

default_error_schema = api.schema('default_error_schema', default_error_schema)

base_movie_entry = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'url': {'type': 'string'},
        'movie_name': {'type': 'string'},
        'movie_year': {'type': 'integer'}
    },
    'additionalProperties': True,
    'required': ['url'],
    'anyOf': [
        {'required': ['title']},
        {'required': ['movie_name', 'movie_year']}
    ]

}

return_movie_entry = copy.deepcopy(base_movie_entry)
return_movie_entry['properties']['id'] = {'type': 'integer'}
return_movie_entry['properties']['list_name'] = {'type': 'string'}

return_movie_list = {
    'type': 'object',
    'properties': {
        'movies': {
            'type': 'array',
            'items': return_movie_entry
        },
        'number_of_movies': {'type': 'integer'},
        'list_name': {'type': 'string'}
    }
}

base_movie_entry_schema = api.schema('base_movie_entry', base_movie_entry)
return_movie_entry_schema = api.schema('return_movie_entry_schema', return_movie_entry)
movie_list_return_schema = api.schema('movie_list_return_model', return_movie_list)


@movie_list_api.route('/<string:list_name>')
@api.doc(params={'list_name': 'Name of the list'})
class MovieListAPI(APIResource):
    @api.response(code_or_apierror=200, model=movie_list_return_schema)
    def get(self, list_name, session=None):
        ''' Get Movie list entries '''
        # TODO Pagination
        movies = [dict(movie) for movie in ml.get_list(list_name)]
        return jsonify({'movies': movies,
                        'number_of_entries': len(movies),
                        'list_name': list_name})

    @api.validate(base_movie_entry_schema)
    @api.response(201, model=return_movie_entry_schema)
    @api.doc(description="This will create a new list if list name doesn't exist")
    def post(self, list_name, session=None):
        ''' Adds a movie to the list. '''
        data = request.json
        movies = ml.get_list(list_name)

        movie = movies.add(data, session=session)
        return movie, 201


@movie_list_api.route('/<string:list_name>/<int:id>/')
@api.doc(params={'list_name': 'Name of the list', 'id': 'ID of the movie'})
class MovieListIDAPI(APIResource):
    @api.response(200, model=return_movie_entry_schema)
    @api.response(404, model=default_error_schema)
    def get(self, list_name, id, session=None):
        ''' Get a specific movie ID '''
        movies = [dict(movie) for movie in ml.get_list(list_name)]
        for movie in movies:
            if movie['id'] == id:
                return movie
        return {'status': 'error',
                'message': 'could not find movie with id %d in list %s'% (id, list_name)}, 404

    @api.validate(base_movie_entry_schema)
    @api.response(200, model=return_movie_entry_schema)
    @api.response(404, model=default_error_schema)
    def put(self, list_name, id, session=None):
        ''' Edit a specific movie ID '''
        data = request.json
        movies = ml.get_list(list_name)
        resolved_movies = [dict(movie) for movie in movies]
        for resolved_movie in resolved_movies:
            if resolved_movie['id'] == id:
                movies.discard(resolved_movie)
                new_movie = movies.add(data)
                return new_movie, 201
        return {'status': 'error',
                'message': 'could not find movie with id %d in list %s'% (id, list_name)}, 404

    @api.response(200, model=empty_response)
    @api.response(404, model=default_error_schema)
    def delete(self, list_name, id, session=None):
        ''' Remove an movie from the list '''
        movies = ml.get_list(list_name)
        resolved_movies = [dict(movie) for movie in movies]
        for resolved_movie in resolved_movies:
            if resolved_movie['id'] == id:
                movies.discard(resolved_movie)
                return {}
        return {'status': 'error',
                'message': 'could not find movie with id %d in list %s'% (id, list_name)}, 404
