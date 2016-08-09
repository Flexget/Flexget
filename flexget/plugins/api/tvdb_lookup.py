from __future__ import unicode_literals, division, absolute_import

from builtins import *  # pylint: disable=unused-import, redefined-builtin
from flask import jsonify
from flask_restplus import inputs

from flexget.api import api, APIResource
from flexget.plugins.internal.api_tvdb import lookup_series, lookup_episode, search_for_series

tvdb_api = api.namespace('tvdb', description='TheTVDB Shows')


class objects_container(object):
    default_error_schema = {
        'type': 'object',
        'properties': {
            'status': {'type': 'string'},
            'message': {'type': 'string'}
        }
    }

    tvdb_series_object = {
        'type': 'object',
        'properties': {
            'tvdb_id': {'type': 'integer'},
            'last_updated': {'type': 'string', 'format': 'date-time'},
            'expired': {'type': 'boolean'},
            'name': {'type': 'string'},
            'rating': {'type': 'number'},
            'status': {'type': 'string'},
            'runtime': {'type': 'integer'},
            'airs_time': {'type': 'string'},
            'airs_dayofweek': {'type': 'string'},
            'content_rating': {'type': 'string'},
            'network': {'type': 'string'},
            'overview': {'type': 'string'},
            'imdb_id': {'type': 'string'},
            'zap2it_id': {'type': 'string'},
            'banner': {'type': 'string'},
            'first_aired': {'type': 'string'},
            'actors': {'type': 'array', 'items': {'type': 'string'}},
            'aliases': {'type': 'array', 'items': {'type': 'string'}},
            'posters': {'type': 'array', 'items': {'type': 'string'}},
            'genres': {'type': 'array', 'items': {'type': 'string'}},
        }
    }

    episode_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'expired': {'type': 'boolean'},
            'last_update': {'type': 'string'},
            'season_number': {'type': 'integer'},
            'episode_number': {'type': 'integer'},
            'absolute_number': {'type': 'integer'},
            'episode_name': {'type': 'string'},
            'overview': {'type': 'string'},
            'director': {'type': 'array', 'items': {'type': 'string'}},
            'writer': {'type': 'array', 'items': {'type': 'string'}},
            'rating': {'type': 'number'},
            'image': {'type': 'string'},
            'first_aired': {'type': 'string'},
            'series_id': {'type': 'integer'}
        }
    }

    search_result_object = {
        'type': 'object',
        'properties': {
            'aliases': {'type': 'array', 'items': {'type': 'string'}},
            'first_aired': {'type': 'string', 'format': 'date-time'},
            'banner': {'type': 'string'},
            'network': {'type': 'string'},
            'series_name': {'type': 'string'},
            'status': {'type': 'string'},
            'overview': {'type': 'string'},
            'tvdb_id': {'type': 'integer'}
        }
    }
    search_results_object = {
        'type': 'object',
        'properties': {
            'search_results': {'type': 'array', 'items': search_result_object}
        }
    }


default_error_schema = api.schema('default_error_schema', objects_container.default_error_schema)
tvdb_series_schema = api.schema('tvdb_series_schema', objects_container.tvdb_series_object)
tvdb_episode_schema = api.schema('tvdb_episode_schema', objects_container.episode_object)
search_results_schema = api.schema('tvdb_search_results_schema', objects_container.search_results_object)

series_parser = api.parser()
series_parser.add_argument('include_actors', type=inputs.boolean, help='Include actors in response')


@tvdb_api.route('/series/<string:title>/')
@api.doc(params={'title': 'TV Show name or TVDB ID'}, parser=series_parser)
class TVDBSeriesSearchApi(APIResource):

    @api.response(200, 'Successfully found show', tvdb_series_schema)
    @api.response(404, 'No show found', default_error_schema)
    def get(self, title, session=None):
        args = series_parser.parse_args()
        try:
            tvdb_id = int(title)
        except ValueError:
            tvdb_id = None

        try:
            if tvdb_id:
                series = lookup_series(tvdb_id=tvdb_id, session=session)
            else:
                series = lookup_series(name=title, session=session)
        except LookupError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404
        result = series.to_dict()
        if args.get('include_actors'):
            result['actors'] = series.actors
        return jsonify(result)


episode_parser = api.parser()
episode_parser.add_argument('season_number', type=int, help='Season number')
episode_parser.add_argument('ep_number', type=int, help='Episode number')
episode_parser.add_argument('absolute_number', type=int, help='Absolute episode number')


@tvdb_api.route('/episode/<int:tvdb_id>/')
@api.doc(params={'tvdb_id': 'TVDB ID of show'}, parser=episode_parser)
class TVDBEpisodeSearchAPI(APIResource):

    @api.response(200, 'Successfully found episode', tvdb_episode_schema)
    @api.response(404, 'No show found', default_error_schema)
    @api.response(500, 'Not enough parameters for lookup', default_error_schema)
    def get(self, tvdb_id, session=None):
        args = episode_parser.parse_args()
        absolute_number = args.get('absolute_number')
        season_number = args.get('season_number')
        ep_number = args.get('ep_number')
        if not ((season_number and ep_number) or absolute_number):
            return {'status': 'error',
                    'message': 'not enough parameters for lookup. Either season and episode number or absolute number '
                               'are required.'
                    }, 500

        kwargs = {'tvdb_id': tvdb_id,
                  'session': session}

        if absolute_number:
            kwargs['absolute_number'] = absolute_number
        if season_number and ep_number:
            kwargs['season_number'] = season_number
            kwargs['episode_number'] = ep_number

        try:
            episode = lookup_episode(**kwargs)
        except LookupError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404
        return jsonify(episode.to_dict())


search_parser = api.parser()
search_parser.add_argument('search_name', help='Series Name')
search_parser.add_argument('imdb_id', help='Series IMDB ID')
search_parser.add_argument('zap2it_id', help='Series ZAP2IT ID')
search_parser.add_argument('force_search', type=inputs.boolean,
                           help='Force online lookup or allow for result to be retrieved from cache')


@tvdb_api.route('/search/')
@api.doc(parser=search_parser)
class TVDBSeriesSearchAPI(APIResource):

    @api.response(200, 'Successfully got results', search_results_schema)
    @api.response(404, 'No results found', default_error_schema)
    @api.response(400, 'Not enough parameters for lookup', default_error_schema)
    def get(self, session=None):
        args = search_parser.parse_args()
        if not (args.get('search_name') or args.get('imdb_id') or args.get('zap2it_id')):
            return {'status': 'error',
                    'message': 'Not enough lookup arguments'
                    }, 400
        kwargs = {
            'search_name': args.get('search_name'),
            'imdb_id': args.get('imdb_id'),
            'zap2it_id': args.get('zap2it_id'),
            'force_search': args.get('force_search'),
            'session': session
        }
        try:
            search_results = search_for_series(**kwargs)
        except LookupError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404
        return jsonify({'search_results': [a.to_dict() for a in search_results]})
