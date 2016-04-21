from __future__ import unicode_literals, division, absolute_import

from flask import jsonify

from flexget.api import api, APIResource
from flexget.plugins.api_trakt import ApiTrakt as at

trakt_api = api.namespace('trakt', description='Trakt lookup endpoint')

default_error_schema = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'}
    }
}

default_error_schema = api.schema('default_error_schema', default_error_schema)

series_return_object = {

}

lookup_parser = api.parser()
lookup_parser.add_argument('title', required=True, help='Lookup title')
lookup_parser.add_argument('year', type=int, help='Lookup year')
lookup_parser.add_argument('trakt_id', type=int, help='Trakt ID')
lookup_parser.add_argument('trakt_slug', help='Trakt slug')
lookup_parser.add_argument('tmdb_id', type=int, help='TMDB ID')
lookup_parser.add_argument('imdb_id', help='IMDB ID')
lookup_parser.add_argument('tvdb_id', type=int, help='TVDB ID')
lookup_parser.add_argument('tvrage_id', type=int, help='TVRage ID')


@trakt_api.route('/series/')
class TraktSeriesSearchApi(APIResource):
    @api.response(200, 'Successfully found show')
    @api.response(404, 'No show found', default_error_schema)
    @api.doc(parser=lookup_parser)
    def get(self, session=None):
        args = lookup_parser.parse_args()
        try:
            result = at.lookup_series(session=session, **args)
        except LookupError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404

        return jsonify(result.to_dict())


@trakt_api.route('/movies/')
class TraktSeriesSearchApi(APIResource):
    @api.response(200, 'Successfully found show')
    @api.response(404, 'No show found', default_error_schema)
    @api.doc(parser=lookup_parser)
    def get(self, session=None):
        args = lookup_parser.parse_args()
        try:
            result = at.lookup_movie(session=session, **args)
        except LookupError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404

        return jsonify(result.to_dict())
