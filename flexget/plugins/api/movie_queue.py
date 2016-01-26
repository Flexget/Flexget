from __future__ import unicode_literals, division, absolute_import

from math import ceil
from operator import itemgetter

from flask import jsonify, request

from flexget.api import api, APIResource
from flexget.plugins.filter import movie_queue as mq
from flexget.utils import qualities

movie_queue_api = api.namespace('movie_queue', description='Movie Queue operations')

movie_object = {
    'type': 'object',
    'properties': {
        'added': {'type': 'string'},
        'downloaded': {'type': 'string'},
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
movie_queue_status_value_enum_list = ['pending', 'downloaded', 'all']


def movie_queue_status_value_enum(value):
    """ Movie queue status enum. Return True for 'downloaded', False for 'pending' and None for 'all' """
    enum = movie_queue_status_value_enum_list
    if isinstance(value, bool):
        return value
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    if value == 'downloaded':
        return True
    elif value == 'pending':
        return False
    else:
        return None


def movie_queue_sort_value_enum(value):
    enum = ['added', 'downloaded', 'id', 'title']
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    return value


def movie_queue_sort_order_enum(value):
    enum = ['desc', 'asc']
    if isinstance(value, bool):
        return value
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    if value == 'desc':
        return True
    return False


movie_queue_schema = api.schema('list_movie_queue', movie_queue_schema)

movie_queue_parser = api.parser()
movie_queue_parser.add_argument('page', type=int, default=1, help='Page number')
movie_queue_parser.add_argument('max', type=int, default=100, help='Movies per page')
movie_queue_parser.add_argument('status', type=movie_queue_status_value_enum, default=False,
                                help='Filter list by status. Filter by {0}. Default is "pending"'.format(
                                        ' ,'.join(movie_queue_status_value_enum_list)))
movie_queue_parser.add_argument('sort_by', type=movie_queue_sort_value_enum, default='added',
                                help="Sort response by 'added', 'downloaded', 'id', 'title'")
movie_queue_parser.add_argument('order', type=movie_queue_sort_order_enum, default='desc',
                                help="Sorting order, can be 'asc' or 'desc'")

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
    @api.response(200, 'Movie queue retrieved successfully', movie_queue_schema)
    @api.doc(parser=movie_queue_parser)
    def get(self, session=None):
        """ List queued movies """
        args = movie_queue_parser.parse_args()
        page = args['page']
        max_results = args['max']
        downloaded = args['status']
        sort_by = args['sort_by']
        order = args['order']
        # Handles default if it explicitly called
        if order == 'desc':
            order = True

        movie_queue = mq.queue_get(session=session, downloaded=downloaded)
        count = len(movie_queue)

        pages = int(ceil(count / float(max_results)))

        movie_items = []

        if page > pages and pages != 0:
            return {'error': 'page %s does not exist' % page}, 404

        start = (page - 1) * max_results
        finish = start + max_results
        if finish > count:
            finish = count

        for movie_number in range(start, finish):
            movie_items.append(movie_queue[movie_number].to_dict())

        sorted_movie_list = sorted(movie_items, key=itemgetter(sort_by), reverse=order)

        return jsonify({
            'movies': sorted_movie_list,
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


@api.response(404, 'Movie not found')
@api.response(400, 'Invalid type received')
@movie_queue_api.route('/<type>/<id>/')
@api.doc(params={'id': 'ID of Queued Movie', 'type': 'Type of ID to be used (imdb/tmdb/movie_id)'},
         description='Remove a movie from movie queue or edit its quality or download status')
class MovieQueueManageAPI(APIResource):
    def validate_type(self, type, id, session):
        if type not in ['imdb', 'tmdb', 'movie_id']:
            reply = {
                'status': 'error',
                'message': 'invalid ID type received. Must be one of (imdb/tmdb/movie_id)'
            }
            return reply, 400
        kwargs = {'session': session}
        if type == 'imdb':
            kwargs['imdb_id'] = id
        elif type == 'tmdb':
            kwargs['tmdb_id'] = id
        elif type == 'movie_id':
            kwargs['movie_id'] = id
        return kwargs

    @api.response(200, 'Movie successfully deleted')
    def delete(self, type, id, session=None):
        """ Delete movies from movie queue """
        kwargs = self.validate_type(type, id, session)
        try:
            mq.queue_del(**kwargs)
        except mq.QueueError as e:
            reply = {'status': 'error',
                     'message': e.message}
            return reply, 404

        reply = jsonify(
                {'status': 'success',
                 'message': 'successfully deleted {0} movie {1}'.format(type, id)})
        return reply

    @api.response(200, 'Movie successfully updated', movie_edit_results_schema)
    @api.validate(movie_edit_input_schema)
    def put(self, type, id, session=None):
        """ Updates movie quality or downloaded state in movie queue """
        kwargs = self.validate_type(type, id, session)
        movie = None
        data = request.json
        if data.get('reset_downloaded'):
            try:
                movie = mq.queue_forget(**kwargs)
            except mq.QueueError as e:
                reply = {
                    'status': 'error',
                    'message': e.message
                }
                return reply, 404

        if data.get('quality'):
            kwargs['quality'] = data['quality']
            try:
                movie = mq.queue_edit(**kwargs)
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
