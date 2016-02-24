from __future__ import unicode_literals, division, absolute_import

import copy
import logging

from flask import jsonify
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource
from flexget.plugins.list import movie_list as ml
from flexget.utils.tools import split_title_year

log = logging.getLogger('movie_list')

movie_list_api = api.namespace('movie_list', description='Movie List operations')

default_error_schema = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'}
    }
}
empty_response = api.schema('empty', {'type': 'object'})

default_error_schema = api.schema('default_error_schema', default_error_schema)
empty_response = api.schema('empty_response', empty_response)

input_movie_list_id_object = {
    'type': 'array',
    'items': {
        'type': 'object',
        'minProperties': 1,
        'additionalProperties': True
    }
}

input_movie_entry = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'url': {'type': 'string'},
        'movie_name': {'type': 'string'},
        'movie_year': {'type': 'integer'},
        'movie_identifiers': input_movie_list_id_object
    },
    'additionalProperties': True,
    'required': ['url'],
    'anyOf': [
        {'required': ['title']},
        {'required': ['movie_name', 'movie_year']}
    ]
}

return_movie_list_id_object = copy.deepcopy(input_movie_list_id_object)
return_movie_list_id_object.update(
    {'properties': {
        'id': {'type': 'integer'},
        'movie_id': {'type': 'integer'}
    }})

movie_list_object = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'year': {'type': 'integer'},
        'list_id': {'type': 'integer'},
        'movie_list_ids': {
            'type': 'array',
            'items': return_movie_list_id_object
        },
    }
}

list_object = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'name': {'type': 'string'}
    }
}

return_movies = {
    'type': 'object',
    'properties': {
        'movies': {
            'type': 'array',
            'items': movie_list_object
        },
        'number_of_movies': {'type': 'integer'}
    }
}
return_lists = {'type': 'array', 'items': list_object}

input_movie_entry_schema = api.schema('input_movie_entry', input_movie_entry)
input_movie_list_id_schema = api.schema('input_movie_list_id_object', input_movie_list_id_object)

movie_list_id_object_schema = api.schema('movie_list_id_object', return_movie_list_id_object)
movie_list_object_schema = api.schema('movie_list_object', movie_list_object)
list_object_schema = api.schema('list_object', list_object)
return_lists_schema = api.schema('return_lists', return_lists)
return_movies_schema = api.schema('return_movies', return_movies)


@movie_list_api.route('/')
class MovieListAPI(APIResource):
    @api.response(200, model=return_lists_schema)
    def get(self, session=None):
        """ Gets all movies lists """
        movie_lists = [movie_list.to_dict() for movie_list in ml.get_all_lists(session=session)]
        return jsonify({'movie_lists': movie_lists})


@movie_list_api.route('/search/<string:list_name>/')
@api.doc(params={'list_name': 'Name of the list(s) to search'})
class MovieListSearchAPI(APIResource):
    @api.response(200, model=return_lists_schema)
    def get(self, list_name, session=None):
        """ Search lists by name """
        movie_lists = [movie_list.to_dict() for movie_list in ml.get_list_by_name(name=list_name, session=session)]
        return jsonify({'movie_lists': movie_lists})


@movie_list_api.route('/<int:list_id>')
@api.doc(params={'list_id': 'ID of the list'})
class MovieListListAPI(APIResource):
    @api.response(404, model=default_error_schema)
    @api.response(200, model=list_object_schema)
    def get(self, list_id, session=None):
        """ Get list by ID """
        try:
            list = ml.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        return jsonify(list.to_dict())

    @api.response(200, model=empty_response)
    @api.response(404, model=default_error_schema)
    def delete(self, list_id, session=None):
        """ Delete list by ID """
        try:
            ml.delete_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        return {}


@movie_list_api.route('/<int:list_id>/movies/')
@api.doc(params={'list_id': 'ID of the list'})
class MovieListMoviesAPI(APIResource):
    @api.response(404, model=default_error_schema)
    @api.response(200, model=return_movies_schema)
    def get(self, list_id, session=None):
        """ Get movies by list ID """
        try:
            list = ml.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        movies = [movie.to_dict() for movie in list.movies]
        return jsonify({'movies': movies})

    @api.validate(input_movie_entry_schema)
    @api.response(201, model=movie_list_object_schema)
    @api.response(404, description='List not found', model=default_error_schema)
    @api.response(500, description='Movie already exist in list', model=default_error_schema)
    def post(self, list_id, session=None):
        """ Add movies to list by ID """
        try:
            list = ml.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        data = request.json
        if 'movie_name' in data:
            title, year = data['movie_name'], data.get('movie_year')
        else:
            title, year = split_title_year(data['title'])
        movie = ml.get_movie_by_title(list_id=list_id, title=title, session=session)
        if movie:
            return {'status': 'error',
                    'message': 'movie with name "%s" already exist in list %d' % (title, list_id)}, 500
        movie = ml.MovieListMovie()
        movie.title = title
        movie.year = year
        movie.ids = ml.get_db_movie_identifiers(identifier_list=data.get('movie_identifiers'), session=session)
        movie.list_id = list_id
        session.add(movie)
        session.commit()
        response = jsonify({'movie': movie.to_dict()})
        response.status_code = 201
        return response


@movie_list_api.route('/<int:list_id>/movies/<int:movie_id>/')
@api.doc(params={'list_id': 'ID of the list', 'movie_id': 'ID of the movie'})
@api.response(404, description='List or movie not found', model=default_error_schema)
class MovieListMovieAPI(APIResource):
    @api.response(200, model=movie_list_object_schema)
    def get(self, list_id, movie_id, session=None):
        """ Get a movie by list ID and movie ID """
        try:
            movie = ml.get_movie_by_id(list_id=list_id, movie_id=movie_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'could not find movie with id %d in list %d' % (movie_id, list_id)}, 404
        return jsonify(movie.to_dict())

    @api.response(200, model=empty_response)
    def delete(self, list_id, movie_id, session=None):
        """ Delete a movie by list ID and movie ID """
        try:
            movie = ml.get_movie_by_id(list_id=list_id, movie_id=movie_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'could not find movie with id %d in list %d' % (movie_id, list_id)}, 404
        session.delete(movie)
        return {}

    @api.validate(input_movie_list_id_schema)
    @api.response(200, model=movie_list_object_schema)
    @api.doc(description='Sent movie identifiers will override any existing identifiers that the movie currently holds')
    def put(self, list_id, movie_id, session=None):
        """ Sets movie identifiers """
        try:
            movie = ml.get_movie_by_id(list_id=list_id, movie_id=movie_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'could not find movie with id %d in list %d' % (movie_id, list_id)}, 404
        data = request.json
        movie.ids[:] = ml.get_db_movie_identifiers(identifier_list=data, movie_id=movie_id, session=session)
        session.commit()
        return movie.to_dict()
