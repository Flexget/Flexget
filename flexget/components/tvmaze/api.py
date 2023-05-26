from flask import jsonify
from flask_restx import inputs

from flexget.api import APIResource, api
from flexget.api.app import BadRequest, NotFoundError, etag
from flexget.components.tvmaze.api_tvmaze import APITVMaze

tvmaze_api = api.namespace('tvmaze', description='TVMaze Shows')


class ObjectsContainer:
    actor_object = {
        'type': 'object',
        'properties': {
            "last_update": {'type': 'string', 'format': 'date-time'},
            "medium_image": {'type': 'string'},
            "name": {'type': 'string'},
            "original_image": {'type': 'string'},
            "tvmaze_id": {'type': 'integer'},
            "url": {'type': 'string'},
        },
    }

    schedule_object = {
        'type': 'object',
        'properties': {
            "days": {'type': 'array', 'items': {'type': 'string'}},
            "time": {'type': 'string'},
        },
    }

    tvmaze_series_object = {
        'type': 'object',
        'properties': {
            'tvmaze_id': {'type': 'integer'},
            'status': {'type': 'string'},
            'rating': {'type': 'number'},
            'genres': {'type': 'array', 'items': {'type': 'string'}},
            'weight': {'type': 'integer'},
            'updated': {'type': 'string', 'format': 'date-time'},
            'name': {'type': 'string'},
            'language': {'type': 'string'},
            'schedule': schedule_object,
            'url': {'type': 'string', 'format': 'url'},
            'original_image': {'type': 'string'},
            'medium_image': {'type': 'string'},
            'tvdb_id': {'type': 'integer'},
            'tvrage_id': {'type': 'integer'},
            'premiered': {'type': 'string', 'format': 'date-time'},
            'year': {'type': 'integer'},
            'summary': {'type': 'string'},
            'webchannel': {'type': ['string', 'null']},
            'runtime': {'type': 'integer'},
            'show_type': {'type': 'string'},
            'network': {'type': ['string', 'null']},
            'last_update': {'type': 'string', 'format': 'date-time'},
        },
        'required': [
            'tvmaze_id',
            'status',
            'rating',
            'genres',
            'weight',
            'updated',
            'name',
            'language',
            'schedule',
            'url',
            'original_image',
            'medium_image',
            'tvdb_id',
            'tvrage_id',
            'premiered',
            'year',
            'summary',
            'webchannel',
            'runtime',
            'show_type',
            'network',
            'last_update',
        ],
        'additionalProperties': False,
    }

    tvmaze_episode_object = {
        'type': 'object',
        'properties': {
            'tvmaze_id': {'type': 'integer'},
            'series_id': {'type': 'integer'},
            'number': {'type': 'integer'},
            'season_number': {'type': 'integer'},
            'title': {'type': 'string'},
            'airdate': {'type': 'string', 'format': 'date-time'},
            'url': {'type': 'string'},
            'original_image': {'type': ['string', 'null']},
            'medium_image': {'type': ['string', 'null']},
            'airstamp': {'type': 'string', 'format': 'date-time'},
            'runtime': {'type': 'integer'},
            'summary': {'type': 'string'},
            'last_update': {'type': 'string', 'format': 'date-time'},
        },
        'required': [
            'tvmaze_id',
            'series_id',
            'number',
            'season_number',
            'title',
            'airdate',
            'url',
            'original_image',
            'medium_image',
            'airstamp',
            'runtime',
            'summary',
            'last_update',
        ],
        'additionalProperties': False,
    }


tvmaze_series_schema = api.schema_model(
    'tvmaze_series_schema', ObjectsContainer.tvmaze_series_object
)
tvmaze_episode_schema = api.schema_model(
    'tvmaze_episode_schema', ObjectsContainer.tvmaze_episode_object
)


@tvmaze_api.route('/series/<string:title>/')
@api.doc(params={'title': 'TV Show name or TVMaze ID'})
class TVDBSeriesSearchApi(APIResource):
    @etag(cache_age=3600)
    @api.response(200, 'Successfully found show', model=tvmaze_series_schema)
    @api.response(NotFoundError)
    def get(self, title, session=None):
        """TVMaze series lookup"""
        try:
            tvmaze_id = int(title)
        except ValueError:
            tvmaze_id = None
        try:
            if tvmaze_id:
                series = APITVMaze.series_lookup(tvmaze_id=tvmaze_id, session=session)
            else:
                series = APITVMaze.series_lookup(series_name=title, session=session)
        except LookupError as e:
            raise NotFoundError(e.args[0])
        return jsonify(series.to_dict())


episode_parser = api.parser()
episode_parser.add_argument('season_num', type=int, help='Season number')
episode_parser.add_argument('ep_num', type=int, help='Episode number')
episode_parser.add_argument(
    'air_date', type=inputs.date_from_iso8601, help="Air date in the format of '2012-01-01'"
)


@tvmaze_api.route('/episode/<int:tvmaze_id>/')
@api.doc(params={'tvmaze_id': 'TVMaze ID of show'})
@api.doc(expect=[episode_parser])
class TVDBEpisodeSearchAPI(APIResource):
    @etag(cache_age=3600)
    @api.response(200, 'Successfully found episode', tvmaze_episode_schema)
    @api.response(NotFoundError)
    @api.response(BadRequest)
    def get(self, tvmaze_id, session=None):
        """TVMaze episode lookup"""
        args = episode_parser.parse_args()
        air_date = args.get('air_date')
        season_num = args.get('season_num')
        ep_num = args.get('ep_num')

        kwargs = {'tvmaze_id': tvmaze_id, 'session': session}
        if air_date:
            kwargs['series_id_type'] = 'date'
            kwargs['series_date'] = air_date
        elif season_num and ep_num:
            kwargs['series_id_type'] = 'ep'
            kwargs['series_season'] = season_num
            kwargs['series_episode'] = ep_num
        else:
            raise BadRequest('not enough parameters sent for lookup')
        try:
            episode = APITVMaze.episode_lookup(**kwargs)
        except LookupError as e:
            raise NotFoundError(e.args[0])
        return jsonify(episode.to_dict())
