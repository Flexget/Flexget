from __future__ import unicode_literals, division, absolute_import

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
        'TVDB_id': {'type': 'integer'},
        'last_updated': {'type': 'string', 'format': 'date-time'},
        'expired': {'type': 'boolean'},
        'series_name': {'type': 'string'},
        'language': {'type': 'string'},
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
        'fan_art': {'type': 'string'},
        'poster': {'type': 'string'},
        'poster_file': {'type': 'string'},
        'genres': {'type': 'array', 'items': {'type': 'string'}},
        'first_aired': {'type': 'string'},
        'actors': {'type': 'array', 'items': {'type': 'string'}}
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
        'guest_stars': {'type': 'array', 'items': {'type': 'string'}},
        'rating': {'type': 'number'},
        'file_name': {'type': 'string'},
        'first_aired': {'type': 'string'},
        'series_id': {'type': 'integer'}
    }
}

tvdb_series_schema = api.schema('tvdb_series_schema', tvdb_series_object)
tvdb_episode_schema = api.schema('tvdb_episode_schema', episode_object)


@tvdb_api.route('/series/<string:search>/')
@api.doc(params={'search': 'TV Show name or TVDB ID'})
class TVDBSeriesSearchApi(APIResource):
    @api.response(200, 'Successfully found show', tvdb_series_schema)
    @api.response(404, 'No show found', default_error_schema)
    def get(self, search, session=None):
        try:
            tvdb_id = int(search)
        except ValueError:
            tvdb_id = None

        try:
            if tvdb_id:
                result = lookup_series(tvdb_id=tvdb_id, session=session)
            else:
                result = lookup_series(name=search, session=session)
        except LookupError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404

        return jsonify(result.to_dict())


episode_parser = api.parser()
episode_parser.add_argument('season_num', type=int, help='Season number')
episode_parser.add_argument('ep_num', type=int, help='Episode number')
episode_parser.add_argument('absolute_num', type=int, help='Absolute episode number')
episode_parser.add_argument('air_date', type=inputs.date_from_iso8601, help="Air date in the format of '2012-01-01'")


@tvdb_api.route('/episode/<int:tvdb_id>/')
@api.doc(params={'tvdb_id': 'TVDB ID of show'})
@api.doc(parser=episode_parser)
class TVDBEpisodeSearchAPI(APIResource):
    @api.response(200, 'Successfully found episode', tvdb_episode_schema)
    @api.response(404, 'No show found', default_error_schema)
    @api.response(500, 'Not enough parameters for lookup', default_error_schema)
    def get(self, tvdb_id, session=None):
        args = episode_parser.parse_args()
        air_date = args.get('air_date')
        absolute_num = args.get('absolute_num')
        season_num = args.get('season_num')
        ep_num = args.get('ep_num')

        kwargs = {'tvdb_id': tvdb_id,
                  'session': session}

        if air_date:
            kwargs['airdate'] = air_date
        elif absolute_num:
            kwargs['absolutenum'] = absolute_num
        elif season_num and ep_num:
            kwargs['seasonnum'] = season_num
            kwargs['episodenum'] = ep_num
        else:
            return {'status': 'error',
                    'message': 'not enough parameters sent for lookup'}, 500
        try:
            episode = lookup_episode(**kwargs)
        except LookupError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404
        return jsonify(episode.to_dict())
