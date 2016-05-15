from __future__ import unicode_literals, division, absolute_import

from builtins import *  # pylint: disable=unused-import, redefined-builtin
from flask import jsonify
from flask_restplus import inputs

from flexget.api import api, APIResource
from flexget.plugins.api_tvdb import lookup_series, lookup_episode

tvdb_api = api.namespace('tvdb', description='TheTVDB Shows')

default_error_schema = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'}
    }
}

default_error_schema = api.schema('default_error_schema', default_error_schema)

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

tvdb_series_schema = api.schema('tvdb_series_schema', tvdb_series_object)
tvdb_episode_schema = api.schema('tvdb_episode_schema', episode_object)

series_parser = api.parser()
series_parser.add_argument('include_actors', type=inputs.boolean, help='Include actors in response')


@tvdb_api.route('/series/<string:search>/')
@api.doc(params={'search': 'TV Show name or TVDB ID'}, parser=series_parser)
class TVDBSeriesSearchApi(APIResource):
    @api.response(200, 'Successfully found show', tvdb_series_schema)
    @api.response(404, 'No show found', default_error_schema)
    def get(self, search, session=None):
        args = series_parser.parse_args()
        try:
            tvdb_id = int(search)
        except ValueError:
            tvdb_id = None

        try:
            if tvdb_id:
                series = lookup_series(tvdb_id=tvdb_id, session=session)
            else:
                series = lookup_series(name=search, session=session)
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
