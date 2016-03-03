from __future__ import unicode_literals, division, absolute_import

from flask import jsonify

from flexget.api import api, APIResource
from flexget.plugins.api_tvmaze import APITVMaze as tvm

tvmaze_api = api.namespace('tvmaze', description='TVMaze Shows')

default_error_schema = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'}
    }
}

default_error_schema = api.schema('default_error_schema', default_error_schema)

actor_object = {
    'type': 'object',
    'properties': {
        "last_update": {'type': 'string', 'format': 'date-time'},
        "medium_image": {'type': 'string'},
        "name": {'type': 'string'},
        "original_image": {'type': 'string'},
        "tvmaze_id": {'type': 'integer'},
        "url": {'type': 'string'},
    }
}

schedule_object = {
    'type': 'object',
    'properties': {
        "days": {'type': 'array', 'items': {'type': 'string'}},
        "time": {'type': 'string'}
    }
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
        'webchannel': {'type': 'string'},
        'runtime': {'type': 'integer'},
        'show_type': {'type': 'string'},
        'network': {'type': 'string'},
        'actors': {'type': 'array', 'items': actor_object},
        'last_update': {'type': 'string', 'format': 'date-time'}
    }
}

tvmaze_series_schema = api.schema('tvmaze_series_schema', tvmaze_series_object)


@tvmaze_api.route('/series/<string:search>/')
@api.doc(params={'search': 'TV Show name or TVMaze ID'})
class TVDBSeriesSearchApi(APIResource):
    @api.response(200, 'Successfully found show', model=tvmaze_series_schema)
    @api.response(404, 'No show found', default_error_schema)
    def get(self, search, session=None):
        try:
            tvmaze_id = int(search)
        except ValueError:
            tvmaze_id = None

        try:
            if tvmaze_id:
                result = tvm.series_lookup(tvmaze_id=tvmaze_id, session=session)
            else:
                result = tvm.series_lookup(series_name=search, session=session)
        except LookupError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404

        return jsonify(result.to_dict())
