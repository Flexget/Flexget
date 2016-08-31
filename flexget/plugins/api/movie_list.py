from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import copy
import logging
from math import ceil

from flask import jsonify
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource, empty_response, default_error_schema
from flexget.plugins.list import movie_list as ml
from flexget.plugins.list.movie_list import MovieListBase
from flexget.utils.tools import split_title_year

log = logging.getLogger('movie_list')

movie_list_api = api.namespace('movie_list', description='Movie List operations')


class ObjectsContainer(object):
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
            'movie_name': {'type': 'string'},
            'movie_year': {'type': 'integer'},
            'movie_identifiers': input_movie_list_id_object
        },
        'additionalProperties': True,
        'required': ['movie_name'],
    }

    return_movie_list_id_object = copy.deepcopy(input_movie_list_id_object)
    return_movie_list_id_object.update(
        {'properties': {
            'id': {'type': 'integer'},
            'added_on': {'type': 'string'},
            'movie_id': {'type': 'integer'}
        }})

    movie_list_object = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'added_on': {'type': 'string'},
            'year': {'type': ['integer', 'null']},
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
            'added_on': {'type': 'string'},
            'name': {'type': 'string'}
        }
    }

    list_input = copy.deepcopy(list_object)
    del list_input['properties']['id']
    del list_input['properties']['added_on']

    return_movies = {
        'type': 'object',
        'properties': {
            'movies': {
                'type': 'array',
                'items': movie_list_object
            },
            'number_of_movies': {'type': 'integer'},
            'total_number_of_movies': {'type': 'integer'},
            'page_number': {'type': 'integer'}
        }
    }

    return_lists = {
        'type': 'object',
        'properties': {
            'movie_lists': {'type': 'array', 'items': list_object}
        }
    }


input_movie_entry_schema = api.schema('input_movie_entry', ObjectsContainer.input_movie_entry)
input_movie_list_id_schema = api.schema('input_movie_list_id_object', ObjectsContainer.input_movie_list_id_object)

movie_list_id_object_schema = api.schema('movie_list_id_object', ObjectsContainer.return_movie_list_id_object)
movie_list_object_schema = api.schema('movie_list_object', ObjectsContainer.movie_list_object)
list_object_schema = api.schema('list_object', ObjectsContainer.list_object)
return_lists_schema = api.schema('return_lists', ObjectsContainer.return_lists)
return_movies_schema = api.schema('return_movies', ObjectsContainer.return_movies)

new_list_schema = api.schema('new_list', ObjectsContainer.list_input)

movie_list_parser = api.parser()
movie_list_parser.add_argument('name', help='Filter results by list name')


@movie_list_api.route('/')
class MovieListAPI(APIResource):
    @api.response(200, model=return_lists_schema)
    @api.doc(parser=movie_list_parser)
    def get(self, session=None):
        """ Gets movies lists """
        args = movie_list_parser.parse_args()
        name = args.get('name')
        movie_lists = [movie_list.to_dict() for movie_list in ml.get_movie_lists(name=name, session=session)]
        return jsonify({'movie_lists': movie_lists})

    @api.validate(new_list_schema)
    @api.response(201, model=list_object_schema)
    @api.response(500, description='List already exist', model=default_error_schema)
    def post(self, session=None):
        """ Create a new list """
        data = request.json
        name = data.get('name')
        try:
            movie_list = ml.get_list_by_exact_name(name=name, session=session)
        except NoResultFound:
            movie_list = None
        if movie_list:
            return {'status': 'error',
                    'message': "list with name '%s' already exists" % name}, 500
        movie_list = ml.MovieListList(name=name)
        session.add(movie_list)
        session.commit()
        resp = jsonify(movie_list.to_dict())
        resp.status_code = 201
        return resp


@movie_list_api.route('/<int:list_id>/')
@api.doc(params={'list_id': 'ID of the list'})
class MovieListListAPI(APIResource):
    @api.response(404, model=default_error_schema)
    @api.response(200, model=list_object_schema)
    def get(self, list_id, session=None):
        """ Get list by ID """
        try:
            movie_list = ml.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        return jsonify(movie_list.to_dict())

    @api.response(200, model=empty_response)
    @api.response(404, model=default_error_schema)
    def delete(self, list_id, session=None):
        """ Delete list by ID """
        try:
            movie_list = ml.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        session.delete(movie_list)
        return {}


movie_identifiers_doc = "Use movie identifier using the following format:\n[{'ID_NAME: 'ID_VALUE'}]."

movies_parser = api.parser()
movies_parser.add_argument('sort_by', choices=('id', 'added', 'title', 'year'), default='title',
                           help='Sort by attribute')
movies_parser.add_argument('order', choices=('desc', 'asc'), default='desc', help='Sorting order')
movies_parser.add_argument('page', type=int, default=1, help='Page number')
movies_parser.add_argument('page_size', type=int, default=10, help='Number of movies per page')


@movie_list_api.route('/<int:list_id>/movies/')
class MovieListMoviesAPI(APIResource):
    @api.response(404, model=default_error_schema)
    @api.response(200, model=return_movies_schema)
    @api.doc(params={'list_id': 'ID of the list'}, parser=movies_parser)
    def get(self, list_id, session=None):
        """ Get movies by list ID """

        args = movies_parser.parse_args()
        page = args.get('page')
        page_size = args.get('page_size')

        start = page_size * (page - 1)
        stop = start + page_size
        descending = bool(args.get('order') == 'desc')

        kwargs = {
            'start': start,
            'stop': stop,
            'list_id': list_id,
            'order_by': args.get('sort_by'),
            'descending': descending,
            'session': session
        }
        try:
            ml.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        count = ml.get_movies_by_list_id(count=True, **kwargs)
        movies = [movie.to_dict() for movie in ml.get_movies_by_list_id(**kwargs)]
        pages = int(ceil(count / float(page_size)))

        number_of_movies = min(page_size, count)

        return jsonify({'movies': movies,
                        'number_of_movies': number_of_movies,
                        'total_number_of_movies': count,
                        'page': page,
                        'total_number_of_pages': pages})

    @api.validate(model=input_movie_entry_schema, description=movie_identifiers_doc)
    @api.response(201, model=movie_list_object_schema)
    @api.response(404, description='List not found', model=default_error_schema)
    @api.response(500, description='Movie already exist in list', model=default_error_schema)
    @api.response(501, description='Movie identifier not allowed', model=default_error_schema)
    def post(self, list_id, session=None):
        """ Add movies to list by ID """
        try:
            ml.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'list_id %d does not exist' % list_id}, 404
        data = request.json
        movie_identifiers = data.get('movie_identifiers', [])
        # Validates ID type based on allowed ID
        # TODO pass this to json schema validation
        for id_name in movie_identifiers:
            if set(id_name.keys()) & set(MovieListBase().supported_ids) == set([]):
                return {'status': 'error',
                        'message': 'movie identifier %s is not allowed' % id_name}, 501
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
        movie.ids = ml.get_db_movie_identifiers(identifier_list=movie_identifiers, session=session)
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
        log.debug('deleting movie %d', movie.id)
        session.delete(movie)
        return {}

    @api.validate(model=input_movie_list_id_schema, description=movie_identifiers_doc)
    @api.response(200, model=movie_list_object_schema)
    @api.response(501, description='Movie identifier not allowed', model=default_error_schema)
    @api.doc(description='Sent movie identifiers will override any existing identifiers that the movie currently holds')
    def put(self, list_id, movie_id, session=None):
        """ Sets movie identifiers """
        try:
            movie = ml.get_movie_by_id(list_id=list_id, movie_id=movie_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'could not find movie with id %d in list %d' % (movie_id, list_id)}, 404
        data = request.json

        # Validates ID type based on allowed ID
        # TODO pass this to json schema validation
        for id_name in data:
            if set(id_name.keys()) & set(MovieListBase().supported_ids) == set([]):
                return {'status': 'error',
                        'message': 'movie identifier %s is not allowed' % id_name}, 501
        movie.ids[:] = ml.get_db_movie_identifiers(identifier_list=data, movie_id=movie_id, session=session)
        session.commit()
        return jsonify(movie.to_dict())
