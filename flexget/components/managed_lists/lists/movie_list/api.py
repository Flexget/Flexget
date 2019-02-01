from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import copy
import logging
from math import ceil

from flask import jsonify
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource
from flexget.api.app import (
    Conflict,
    NotFoundError,
    base_message_schema,
    success_response,
    BadRequest,
    etag,
    pagination_headers,
)
from .movie_list import MovieListBase
from . import db

log = logging.getLogger('movie_list')

movie_list_api = api.namespace('movie_list', description='Movie List operations')


class ObjectsContainer(object):
    input_movie_list_id_object = {
        'type': 'array',
        'items': {'type': 'object', 'minProperties': 1, 'additionalProperties': True},
    }

    input_movie_entry = {
        'type': 'object',
        'properties': {
            'movie_name': {'type': 'string'},
            'movie_year': {'type': 'integer'},
            'movie_identifiers': input_movie_list_id_object,
        },
        'additionalProperties': True,
        'required': ['movie_name'],
    }

    return_movie_list_id_object = copy.deepcopy(input_movie_list_id_object)
    return_movie_list_id_object.update(
        {
            'properties': {
                'id': {'type': 'integer'},
                'added_on': {'type': 'string'},
                'movie_id': {'type': 'integer'},
            }
        }
    )

    movie_list_object = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'added_on': {'type': 'string'},
            'year': {'type': ['integer', 'null']},
            'list_id': {'type': 'integer'},
            'movie_list_ids': {'type': 'array', 'items': return_movie_list_id_object},
        },
    }

    list_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'added_on': {'type': 'string'},
            'name': {'type': 'string'},
        },
    }

    list_input = copy.deepcopy(list_object)
    del list_input['properties']['id']
    del list_input['properties']['added_on']

    return_movies = {'type': 'array', 'items': movie_list_object}

    return_lists = {'type': 'array', 'items': list_object}

    return_identifiers = {'type': 'array', 'items': {'type': 'string'}}


input_movie_entry_schema = api.schema_model(
    'input_movie_entry', ObjectsContainer.input_movie_entry
)
input_movie_list_id_schema = api.schema_model(
    'input_movie_list_id_object', ObjectsContainer.input_movie_list_id_object
)

movie_list_id_object_schema = api.schema_model(
    'movie_list_id_object', ObjectsContainer.return_movie_list_id_object
)
movie_list_object_schema = api.schema_model(
    'movie_list_object', ObjectsContainer.movie_list_object
)
list_object_schema = api.schema_model('list_object', ObjectsContainer.list_object)
return_lists_schema = api.schema_model('return_lists', ObjectsContainer.return_lists)
return_movies_schema = api.schema_model('return_movies', ObjectsContainer.return_movies)

new_list_schema = api.schema_model('new_list', ObjectsContainer.list_input)
identifiers_schema = api.schema_model(
    'movie_list.identifiers', ObjectsContainer.return_identifiers
)

movie_list_parser = api.parser()
movie_list_parser.add_argument('name', help='Filter results by list name')


@movie_list_api.route('/')
class MovieListAPI(APIResource):
    @etag
    @api.response(200, model=return_lists_schema)
    @api.doc(parser=movie_list_parser)
    def get(self, session=None):
        """ Gets movies lists """
        args = movie_list_parser.parse_args()
        name = args.get('name')
        movie_lists = [
            movie_list.to_dict() for movie_list in db.get_movie_lists(name=name, session=session)
        ]
        return jsonify(movie_lists)

    @api.validate(new_list_schema)
    @api.response(201, model=list_object_schema)
    @api.response(Conflict)
    def post(self, session=None):
        """ Create a new list """
        data = request.json
        name = data.get('name')
        try:
            movie_list = db.get_list_by_exact_name(name=name, session=session)
        except NoResultFound:
            movie_list = None
        if movie_list:
            raise Conflict('list with name \'%s\' already exists' % name)
        movie_list = db.MovieListList(name=name)
        session.add(movie_list)
        session.commit()
        resp = jsonify(movie_list.to_dict())
        resp.status_code = 201
        return resp


@movie_list_api.route('/<int:list_id>/')
@api.doc(params={'list_id': 'ID of the list'})
class MovieListListAPI(APIResource):
    @etag
    @api.response(NotFoundError)
    @api.response(200, model=list_object_schema)
    def get(self, list_id, session=None):
        """ Get list by ID """
        try:
            movie_list = db.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)
        return jsonify(movie_list.to_dict())

    @api.response(200, model=base_message_schema)
    @api.response(404)
    def delete(self, list_id, session=None):
        """ Delete list by ID """
        try:
            movie_list = db.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)
        session.delete(movie_list)
        return success_response('successfully deleted list')


movie_identifiers_doc = (
    "Use movie identifier using the following format:\n[{'ID_NAME: 'ID_VALUE'}]."
)

sort_choices = ('id', 'added', 'title', 'year')
movies_parser = api.pagination_parser(sort_choices=sort_choices, default='title')


@movie_list_api.route('/<int:list_id>/movies/')
class MovieListMoviesAPI(APIResource):
    @etag
    @api.response(NotFoundError)
    @api.response(200, model=return_movies_schema)
    @api.doc(params={'list_id': 'ID of the list'}, parser=movies_parser)
    def get(self, list_id, session=None):
        """ Get movies by list ID """
        args = movies_parser.parse_args()

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        start = per_page * (page - 1)
        stop = start + per_page
        descending = sort_order == 'desc'

        kwargs = {
            'start': start,
            'stop': stop,
            'list_id': list_id,
            'order_by': sort_by,
            'descending': descending,
            'session': session,
        }
        try:
            list = db.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)

        total_items = list.movies.count()

        if not total_items:
            return jsonify([])

        movies = [movie.to_dict() for movie in db.get_movies_by_list_id(**kwargs)]

        total_pages = int(ceil(total_items / float(per_page)))

        if page > total_pages:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(len(movies), per_page)

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Create response
        rsp = jsonify(movies)

        # Add link header to response
        rsp.headers.extend(pagination)
        return rsp

    @api.validate(model=input_movie_entry_schema, description=movie_identifiers_doc)
    @api.response(201, model=movie_list_object_schema)
    @api.response(NotFoundError)
    @api.response(Conflict)
    @api.response(BadRequest)
    def post(self, list_id, session=None):
        """ Add movies to list by ID """
        try:
            db.get_list_by_id(list_id=list_id, session=session)
        except NoResultFound:
            raise NotFoundError('list_id %d does not exist' % list_id)
        data = request.json
        movie_identifiers = data.get('movie_identifiers', [])
        # Validates ID type based on allowed ID
        for id_name in movie_identifiers:
            if list(id_name)[0] not in MovieListBase().supported_ids:
                raise BadRequest('movie identifier %s is not allowed' % id_name)
        title, year = data['movie_name'], data.get('movie_year')
        movie = db.get_movie_by_title_and_year(
            list_id=list_id, title=title, year=year, session=session
        )
        if movie:
            raise Conflict('movie with name "%s" already exist in list %d' % (title, list_id))
        movie = db.MovieListMovie()
        movie.title = title
        movie.year = year
        movie.ids = db.get_db_movie_identifiers(identifier_list=movie_identifiers, session=session)
        movie.list_id = list_id
        session.add(movie)
        session.commit()
        response = jsonify(movie.to_dict())
        response.status_code = 201
        return response


@movie_list_api.route('/<int:list_id>/movies/<int:movie_id>/')
@api.doc(params={'list_id': 'ID of the list', 'movie_id': 'ID of the movie'})
@api.response(NotFoundError)
class MovieListMovieAPI(APIResource):
    @etag
    @api.response(200, model=movie_list_object_schema)
    def get(self, list_id, movie_id, session=None):
        """ Get a movie by list ID and movie ID """
        try:
            movie = db.get_movie_by_id(list_id=list_id, movie_id=movie_id, session=session)
        except NoResultFound:
            raise NotFoundError('could not find movie with id %d in list %d' % (movie_id, list_id))
        return jsonify(movie.to_dict())

    @api.response(200, model=base_message_schema)
    def delete(self, list_id, movie_id, session=None):
        """ Delete a movie by list ID and movie ID """
        try:
            movie = db.get_movie_by_id(list_id=list_id, movie_id=movie_id, session=session)
        except NoResultFound:
            raise NotFoundError('could not find movie with id %d in list %d' % (movie_id, list_id))
        log.debug('deleting movie %d', movie.id)
        session.delete(movie)
        return success_response('successfully deleted movie %d' % movie_id)

    @api.validate(model=input_movie_list_id_schema, description=movie_identifiers_doc)
    @api.response(200, model=movie_list_object_schema)
    @api.response(BadRequest)
    @api.doc(
        description='Sent movie identifiers will override any existing identifiers that the movie currently holds'
    )
    def put(self, list_id, movie_id, session=None):
        """ Sets movie identifiers """
        try:
            movie = db.get_movie_by_id(list_id=list_id, movie_id=movie_id, session=session)
        except NoResultFound:
            raise NotFoundError('could not find movie with id %d in list %d' % (movie_id, list_id))
        data = request.json

        # Validates ID type based on allowed ID
        for id_name in data:
            if list(id_name)[0] not in MovieListBase().supported_ids:
                raise BadRequest('movie identifier %s is not allowed' % id_name)
        movie.ids[:] = db.get_db_movie_identifiers(
            identifier_list=data, movie_id=movie_id, session=session
        )
        session.commit()
        return jsonify(movie.to_dict())


@movie_list_api.route('/identifiers/')
@api.doc(description='A list of valid movie identifiers to be used when creating or editing movie')
class MovieListIdentifiers(APIResource):
    @api.response(200, model=identifiers_schema)
    def get(self, session=None):
        """ Return a list of supported movie list identifiers """
        return jsonify(MovieListBase().supported_ids)
