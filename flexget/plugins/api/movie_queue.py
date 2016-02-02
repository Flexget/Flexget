from __future__ import unicode_literals, division, absolute_import

import datetime
from math import ceil

from flask import jsonify, request
from flask_restplus import inputs

from flexget.api import api, APIResource
from flexget.plugins.api.series import NoResultFound
from flexget.plugins.filter import movie_queue as mq
from flexget.utils import qualities

movie_queue_api = api.namespace('movie_queue', description='Movie Queue operations')

movie_object = {
    'type': 'object',
    'properties': {
        'added_date': {'type': 'string'},
        'is_downloaded': {'type': 'boolean'},
        'download_date': {'type': 'string'},
        'entry_original_url': {'type': 'string'},
        'entry_title': {'type': 'string'},
        'entry_url': {'type': 'string'},
        'id': {'type': 'integer'},
        'imdb_id': {'type': 'string'},
        'quality': {'type': 'string'},
        'title': {'type': 'string'},
        'tmdb_id': {'type': 'string'},
    }
}
movie_object_schema = api.schema('movie_object', movie_object)

movie_queue_schema = {
    'type': 'object',
    'properties': {
        'movies': {
            'type': 'array',
            'items': movie_object
        },
        'number_of_movies': {'type': 'integer'},
        'total_number_of_pages': {'type': 'integer'},
        'page_number': {'type': 'integer'}

    }
}

movie_queue_schema = api.schema('list_movie_queue', movie_queue_schema)

movie_queue_parser = api.parser()
movie_queue_parser.add_argument('page', type=int, default=1, help='Page number')
movie_queue_parser.add_argument('max', type=int, default=100, help='Movies per page')
movie_queue_parser.add_argument('is_downloaded', type=inputs.boolean, help='Filter list by movies download status')
movie_queue_parser.add_argument('sort_by', choices=('added', 'is_downloaded', 'id', 'title', 'download_date'),
                                default='added', help="Sort response by attribute")
movie_queue_parser.add_argument('order', choices=('asc', 'desc'), default='desc', help="Sorting order")

movie_add_results_schema = {
    'type': 'object',
    'properties': {
        'message': {'type': 'string'},
        'movie': movie_object
    }
}

movie_add_input_schema = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'imdb_id': {'type': 'string', 'pattern': r'tt\d{7}'},
        'tmdb_id': {'type': 'integer'},
        'quality': {'type': 'string', 'format': 'quality_requirements', 'default': 'any'}
    },
    'anyOf': [
        {'required': ['title']},
        {'required': ['imdb_id']},
        {'required': ['tmdb_id']}
    ]
}

movie_add_results_schema = api.schema('movie_add_results', movie_add_results_schema)
movie_add_input_schema = api.schema('movie_add_input_schema', movie_add_input_schema)

movie_edit_results_schema = {
    'type': 'object',
    'properties': {
        'message': {'type': 'string'},
        'movie': movie_object
    }
}

movie_edit_input_schema = {
    'type': 'object',
    'properties': {
        'quality': {'type': 'string', 'format': 'quality_requirements'},
        'reset_downloaded': {'type': 'boolean', 'default': False}
    },
    'anyOf': [
        {'required': ['quality']},
        {'required': ['reset_downloaded']}
    ]
}

movie_edit_results_schema = api.schema('movie_edit_results_schema', movie_edit_results_schema)
movie_edit_input_schema = api.schema('movie_edit_input_schema', movie_edit_input_schema)


@movie_queue_api.route('/')
@api.doc(description='Get queued movies from list or add a new movie')
class MovieQueueAPI(APIResource):
    @api.response(404, 'Page does not exist')
    @api.response(code_or_apierror=200, model=movie_queue_schema)
    @api.doc(parser=movie_queue_parser, description='test')
    def get(self, session=None):
        """ List queued movies """
        args = movie_queue_parser.parse_args()
        page = args['page']
        max_results = args['max']
        downloaded = args['is_downloaded']
        sort_by = args['sort_by']
        order = args['order']
        # Handles default if it explicitly called
        if order == 'desc':
            order = True
        else:
            order = False

        raw_movie_queue = mq.queue_get(session=session, downloaded=downloaded)
        converted_movie_queue = [movie.to_dict() for movie in raw_movie_queue]
        sorted_movie_list = sorted(converted_movie_queue,
                                   key=lambda movie: movie[sort_by] if movie[sort_by] else datetime.datetime,
                                   reverse=order)

        count = len(sorted_movie_list)
        pages = int(ceil(count / float(max_results)))
        if page > pages and pages != 0:
            return {'error': 'page %s does not exist' % page}, 404

        start = (page - 1) * max_results
        finish = start + max_results
        if finish > count:
            finish = count

        movie_items = []
        for movie_number in range(start, finish):
            movie_items.append(sorted_movie_list[movie_number])

        return jsonify({
            'movies': movie_items,
            'number_of_movies': count,
            'page_number': page,
            'total_number_of_pages': pages
        })

    @api.response(400, 'Page not found')
    @api.response(201, 'Movie successfully added', movie_add_results_schema)
    @api.validate(movie_add_input_schema)
    def post(self, session=None):
        """ Add movies to movie queue """
        kwargs = request.json
        kwargs['quality'] = qualities.Requirements(kwargs.get('quality'))
        kwargs['session'] = session

        try:
            movie = mq.queue_add(**kwargs)
        except mq.QueueError as e:
            reply = {
                'status': 'error',
                'message': e.message
            }
            return reply, 404

        reply = jsonify(
                {
                    'message': 'Successfully added movie to movie queue',
                    'movie': movie
                }
        )
        reply.status_code = 201
        return reply


@api.response(404, 'ID not found')
@movie_queue_api.route('/<id>/')
@api.doc(params={'id': 'ID of Queued Movie',},
         description='Get, remove or edit a movie from movie queue')
class MovieQueueManageAPI(APIResource):
    @api.response(200, 'Movie successfully retrieved', movie_object_schema)
    def get(self, id, session=None):
        """ Returns a movie from queue by ID """
        try:
            movie = mq.get_movie_by_id(movie_id=id)
        except NoResultFound as e:
            return {'status': 'error',
                    'message': 'movie with ID {0} was not found'.format(id)}, 404
        return jsonify(movie)

    @api.response(200, 'Movie successfully deleted')
    def delete(self, id, session=None):
        """ Delete movies from movie queue """
        try:
            mq.queue_del(movie_id=id)
        except mq.QueueError as e:
            reply = {'status': 'error',
                     'message': e.message}
            return reply, 404

        reply = jsonify(
                {'status': 'success',
                 'message': 'successfully deleted movie with ID {0}'.format(id)})
        return reply

    @api.response(200, 'Movie successfully updated', movie_edit_results_schema)
    @api.validate(model=movie_edit_input_schema,
                  description='Values to use when editing existing movie. At least one value should be used')
    def put(self, id, session=None):
        """ Updates movie quality or downloaded state in movie queue """
        movie = None
        data = request.json
        if data.get('reset_downloaded'):
            try:
                movie = mq.queue_forget(movie_id=id)
            except mq.QueueError as e:
                reply = {
                    'status': 'error',
                    'message': e.message
                }
                return reply, 404

        if data.get('quality'):
            try:
                movie = mq.queue_edit(quality=data['quality'], movie_id=id)
            except mq.QueueError as e:
                reply = {'status': 'error',
                         'message': e.message}
                return reply, 404
        if not movie:
            return {'status': 'error',
                    'message': 'Not enough parameters to edit movie data'}, 400

        return jsonify(
                {
                    'status': 'success',
                    'message': 'Successfully updated movie details',
                    'movie': movie
                }
        )
