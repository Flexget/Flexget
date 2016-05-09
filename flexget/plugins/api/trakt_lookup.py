from __future__ import unicode_literals, division, absolute_import

import copy

from flask import jsonify

from flexget.api import api, APIResource
from flexget.plugins.api_trakt import ApiTrakt as at

trakt_api = api.namespace('trakt', description='Trakt lookup endpoint')


class objects_container(object):
    images_object = {'type': 'array', 'items': {'type': 'string'}}

    actor_object = {
        'type': 'object',
        'properties': {
            "imdb_id": {'type': 'string'},
            "name": {'type': 'string'},
            "tmdb_id": {'type': 'integer'},
            "trakt_id": {'type': 'integer'},
            "images": images_object,
            "trakt_slug": {'type': 'string'},
            "birthday": {'type': 'string'},
            "biography": {'type': 'string'},
            "homepage": {'type': 'string'},
            "death": {'type': 'string'}
        }
    }

    base_return_object = {
        'type': 'object',
        'properties': {
            'actors': {'type': 'array', 'items': actor_object},
            'cached_at': {'type': 'string', 'format': 'date-time'},
            'genres': {'type': 'array', 'items': 'string'},
            'id': {'type': 'integer'},
            "overview": {'type': 'string'},
            "runtime": {'type': 'integer'},
            "rating": {'type': 'number'},
            "votes": {'type': 'integer'},
            "language": {'type': 'string'},
            "updated_at": {'type': 'string', 'format': 'date-time'},
            "images": images_object
        }
    }

    series_return_object = copy.deepcopy(base_return_object)
    series_return_object['properties']['tvdb_id'] = {'type': 'integer'}
    series_return_object['properties']['tvrage_id'] = {'type': 'integer'}
    series_return_object['properties']['first_aired'] = {'type': 'string', 'format': 'date-time'}
    series_return_object['properties']['air_day'] = {'type': 'string'}
    series_return_object['properties']['air_time'] = {'type': 'string'}
    series_return_object['properties']['certification'] = {'type': 'string'}
    series_return_object['properties']['network'] = {'type': 'string'}
    series_return_object['properties']['country'] = {'type': 'string'}
    series_return_object['properties']['status'] = {'type': 'string'}
    series_return_object['properties']['aired_episodes'] = {'type': 'integer'}

    movie_return_object = copy.deepcopy(base_return_object)
    movie_return_object['properties']['tagline'] = {'type': 'string'}
    movie_return_object['properties']['released'] = {'type': 'string'}

    default_error_object = {
        'type': 'object',
        'properties': {
            'status': {'type': 'string'},
            'message': {'type': 'string'}
        }
    }


default_error_schema = api.schema('default_error_schema', objects_container.default_error_object)
series_return_schema = api.schema('series_return_schema', objects_container.series_return_object)
movie_return_schema = api.schema('movie_return_schema', objects_container.movie_return_object)

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
    @api.response(200, 'Successfully found show', series_return_schema)
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


@trakt_api.route('/movie/')
class TraktMovieSearchApi(APIResource):
    @api.response(200, 'Successfully found show', movie_return_schema)
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
