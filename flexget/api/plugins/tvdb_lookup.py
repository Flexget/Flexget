from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from flask import jsonify
from flask_restplus import inputs

from flexget.api import api, APIResource
from flexget.api.app import NotFoundError, BadRequest, etag
from flexget.plugins.internal.api_tvdb import lookup_series, lookup_episode, search_for_series

tvdb_api = api.namespace('tvdb', description='TheTVDB Shows')


class ObjectsContainer(object):
    tvdb_series_object = {
        'type': 'object',
        'properties': {
            'tvdb_id': {'type': 'integer'},
            'last_updated': {'type': 'string', 'format': 'date-time'},
            'expired': {'type': 'boolean'},
            'series_name': {'type': 'string'},
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
            'language': {'type': 'string'}
        },
        'required': ['tvdb_id', 'last_updated', 'expired', 'series_name', 'rating', 'status', 'runtime', 'airs_time',
                     'airs_dayofweek', 'content_rating', 'network', 'overview', 'imdb_id', 'zap2it_id', 'banner',
                     'first_aired', 'aliases', 'posters', 'genres', 'language'],
        'additionalProperties': False
    }

    episode_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'expired': {'type': 'boolean'},
            'last_update': {'type': 'integer'},
            'season_number': {'type': 'integer'},
            'episode_number': {'type': 'integer'},
            'absolute_number': {'type': ['integer', 'null']},
            'episode_name': {'type': 'string'},
            'overview': {'type': 'string'},
            'director': {'type': 'string'},
            'rating': {'type': 'number'},
            'image': {'type': ['string', 'null']},
            'first_aired': {'type': 'string'},
            'series_id': {'type': 'integer'}
        },
        'required': ['id', 'expired', 'last_update', 'season_number', 'episode_number', 'absolute_number',
                     'episode_name', 'overview', 'director', 'rating', 'image', 'first_aired', 'series_id'],
        'additionalProperties': False
    }

    search_result_object = {
        'type': 'object',
        'properties': {
            'aliases': {'type': 'array', 'items': {'type': 'string'}},
            'first_aired': {'type': 'string', 'format': 'date-time'},
            'banner': {'type': ['string', 'null']},
            'network': {'type': 'string'},
            'series_name': {'type': 'string'},
            'status': {'type': 'string'},
            'overview': {'type': ['string', 'null']},
            'tvdb_id': {'type': 'integer'}
        },
        'required': ['aliases', 'first_aired', 'banner', 'network', 'series_name', 'status', 'overview', 'tvdb_id'],
        'additionalProperties': False
    }
    search_results_object = {'type': 'array', 'items': search_result_object}


tvdb_series_schema = api.schema('tvdb_series_schema', ObjectsContainer.tvdb_series_object)
tvdb_episode_schema = api.schema('tvdb_episode_schema', ObjectsContainer.episode_object)
search_results_schema = api.schema('tvdb_search_results_schema', ObjectsContainer.search_results_object)

base_parser = api.parser()
base_parser.add_argument('language', default='en', help='Language abbreviation string for different language support')

series_parser = base_parser.copy()
series_parser.add_argument('include_actors', type=inputs.boolean, help='Include actors in response')


@tvdb_api.route('/series/<string:title>/')
@api.doc(params={'title': 'TV Show name or TVDB ID'}, parser=series_parser)
class TVDBSeriesLookupAPI(APIResource):
    @etag
    @api.response(200, 'Successfully found show', tvdb_series_schema)
    @api.response(NotFoundError)
    def get(self, title, session=None):
        """TheTVDB series lookup"""
        args = series_parser.parse_args()
        language = args['language']

        try:
            tvdb_id = int(title)
        except ValueError:
            tvdb_id = None

        kwargs = {'session': session,
                  'language': language}

        if tvdb_id:
            kwargs['tvdb_id'] = tvdb_id
        else:
            kwargs['name'] = title

        try:
            series = lookup_series(**kwargs)
        except LookupError as e:
            raise NotFoundError(e.args[0])

        result = series.to_dict()
        if args.get('include_actors'):
            result['actors'] = series.actors
        return jsonify(result)


episode_parser = base_parser.copy()
episode_parser.add_argument('season_number', type=int, help='Season number')
episode_parser.add_argument('ep_number', type=int, help='Episode number')
episode_parser.add_argument('absolute_number', type=int, help='Absolute episode number')
episode_parser.add_argument('air_date', type=inputs.date, help='Episode airdate in `YYYY-mm-dd` format')


@tvdb_api.route('/episode/<int:tvdb_id>/')
@api.doc(params={'tvdb_id': 'TVDB ID of show'}, parser=episode_parser)
class TVDBEpisodeSearchAPI(APIResource):
    @etag
    @api.response(200, 'Successfully found episode', tvdb_episode_schema)
    @api.response(NotFoundError)
    @api.response(BadRequest)
    def get(self, tvdb_id, session=None):
        """TheTVDB episode lookup"""
        args = episode_parser.parse_args()
        language = args['language']

        absolute_number = args.get('absolute_number')
        season_number = args.get('season_number')
        ep_number = args.get('ep_number')
        air_date = args.get('air_date')

        if not ((season_number and ep_number) or absolute_number or air_date):
            raise BadRequest('not enough parameters for lookup. Either season and episode number or absolute number '
                             'are required.')
        kwargs = {'tvdb_id': tvdb_id,
                  'session': session,
                  'language': language}

        if absolute_number:
            kwargs['absolute_number'] = absolute_number
        if season_number and ep_number:
            kwargs['season_number'] = season_number
            kwargs['episode_number'] = ep_number
        if air_date:
            kwargs['first_aired'] = air_date

        try:
            episode = lookup_episode(**kwargs)
        except LookupError as e:
            raise NotFoundError(e.args[0])
        return jsonify(episode.to_dict())


search_parser = base_parser.copy()
search_parser.add_argument('search_name', help='Series Name')
search_parser.add_argument('imdb_id', help='Series IMDB ID')
search_parser.add_argument('zap2it_id', help='Series ZAP2IT ID')
search_parser.add_argument('force_search', type=inputs.boolean,
                           help='Force online lookup or allow for result to be retrieved from cache')


@tvdb_api.route('/search/')
@api.doc(parser=search_parser)
class TVDBSeriesSearchAPI(APIResource):
    @etag
    @api.response(200, 'Successfully got results', search_results_schema)
    @api.response(BadRequest)
    @api.response(NotFoundError)
    def get(self, session=None):
        """TheTVDB series search"""
        args = search_parser.parse_args()
        language = args['language']

        search_name = args.get('search_name')
        imdb_id = args.get('imdb_id')
        zap2it_id = args.get('zap2it_id')
        force_search = args.get('force_search')

        if not any(arg for arg in [search_name, imdb_id, zap2it_id]):
            raise BadRequest('Not enough lookup arguments')
        kwargs = {
            'search_name': search_name,
            'imdb_id': imdb_id,
            'zap2it_id': zap2it_id,
            'force_search': force_search,
            'session': session,
            'language': language
        }
        try:
            search_results = search_for_series(**kwargs)
        except LookupError as e:
            raise NotFoundError(e.args[0])
        return jsonify([a.to_dict() for a in search_results])
