from __future__ import unicode_literals, division, absolute_import

import copy

from flask import jsonify
from flask_restplus import inputs

from flexget.api import api, APIResource
from flexget.api.app import NotFoundError, etag
from flexget.plugins.internal.api_trakt import ApiTrakt as at, list_actors, get_translations_dict

trakt_api = api.namespace('trakt', description='Trakt lookup endpoint')


class ObjectsContainer(object):
    translation_object = {
        'type': 'object',
        'patternProperties': {
            '^[/d]$': {'type': 'object',
                       'properties': {
                           'overview': {'type': 'string'},
                           'tagline': {'type': 'string'},
                           'title': {'type': 'string'},
                       },
                       'required': ['overview', 'tagline', 'title'],
                       'additionalProperties': False}
        }
    }

    actor_object = {
        'type': 'object',
        'patternProperties': {
            '^[/d]$': {
                'type': 'object',
                'properties': {
                    'imdb_id': {'type': 'string'},
                    'name': {'type': 'string'},
                    'tmdb_id': {'type': 'integer'},
                    'trakt_id': {'type': 'integer'},
                    'trakt_slug': {'type': 'string'},
                    'birthday': {'type': 'string'},
                    'biography': {'type': ['string', 'null']},
                    'homepage': {'type': 'string'},
                    'death': {'type': ['string', 'null']}
                },
                'required': ['imdb_id', 'name', 'tmdb_id', 'trakt_id', 'trakt_slug', 'birthday', 'biography',
                             'homepage', 'death'],
                'additionalProperties': False
            }}
    }

    base_return_object = {
        'type': 'object',
        'properties': {
            'translations': translation_object,
            'actors': actor_object,
            'cached_at': {'type': 'string', 'format': 'date-time'},
            'genres': {'type': 'array', 'items': {'type': 'string'}},
            'id': {'type': 'integer'},
            'overview': {'type': ['string', 'null']},
            'runtime': {'type': ['integer', 'null']},
            'rating': {'type': ['number', 'null']},
            'votes': {'type': ['integer', 'null']},
            'language': {'type': ['string', 'null']},
            'updated_at': {'type': 'string', 'format': 'date-time'},
            'title': {'type': 'string'},
            'year': {'type': ['integer', 'null']},
            'homepage': {'type': ['string', 'null']},
            'slug': {'type': ['string', 'null']},
            'tmdb_id': {'type': ['integer', 'null']},
            'imdb_id': {'type': ['string', 'null']}
        },
        'required': ['cached_at', 'genres', 'id', 'overview', 'runtime', 'rating', 'votes', 'language', 'updated_at',
                     'title', 'year', 'homepage', 'slug', 'tmdb_id', 'imdb_id'],
        'additionalProperties': False
    }

    series_return_object = copy.deepcopy(base_return_object)
    series_return_object['properties']['tvdb_id'] = {'type': ['integer', 'null']}
    series_return_object['properties']['tvrage_id'] = {'type': ['integer', 'null']}
    series_return_object['properties']['first_aired'] = {'type': ['string', 'null'], 'format': 'date-time'}
    series_return_object['properties']['air_day'] = {'type': ['string', 'null']}
    series_return_object['properties']['air_time'] = {'type': ['string', 'null']}
    series_return_object['properties']['certification'] = {'type': ['string', 'null']}
    series_return_object['properties']['network'] = {'type': ['string', 'null']}
    series_return_object['properties']['country'] = {'type': ['string', 'null']}
    series_return_object['properties']['status'] = {'type': 'string'}
    series_return_object['properties']['timezone'] = {'type': ['string', 'null']}
    series_return_object['properties']['number_of_aired_episodes'] = {'type': ['integer', 'null']}
    series_return_object['required'] += ['tvdb_id', 'tvrage_id', 'first_aired', 'air_day', 'air_time', 'certification',
                                         'network', 'country', 'status', 'timezone', 'number_of_aired_episodes']

    movie_return_object = copy.deepcopy(base_return_object)
    movie_return_object['properties']['tagline'] = {'type': 'string'}
    movie_return_object['properties']['released'] = {'type': 'string'}
    movie_return_object['properties']['trailer'] = {'type': ['string', 'null']}
    movie_return_object['required'] += ['tagline', 'released', 'trailer']


series_return_schema = api.schema_model('series_return_schema', ObjectsContainer.series_return_object)
movie_return_schema = api.schema_model('movie_return_schema', ObjectsContainer.movie_return_object)

lookup_parser = api.parser()
lookup_parser.add_argument('year', type=int, help='Lookup year')
lookup_parser.add_argument('trakt_id', type=int, help='Trakt ID')
lookup_parser.add_argument('trakt_slug', help='Trakt slug')
lookup_parser.add_argument('tmdb_id', type=int, help='TMDB ID')
lookup_parser.add_argument('imdb_id', help='IMDB ID')
lookup_parser.add_argument('tvdb_id', type=int, help='TVDB ID')
lookup_parser.add_argument('tvrage_id', type=int, help='TVRage ID')
lookup_parser.add_argument('include_actors', type=inputs.boolean, help='Include actors in response')
lookup_parser.add_argument('include_translations', type=inputs.boolean, help='Include translations in response')


@trakt_api.route('/series/<string:title>/')
@api.doc(params={'title': 'Series name'})
class TraktSeriesSearchApi(APIResource):
    @etag(cache_age=3600)
    @api.response(200, 'Successfully found show', series_return_schema)
    @api.response(NotFoundError)
    @api.doc(parser=lookup_parser)
    def get(self, title, session=None):
        """Trakt series lookup"""
        args = lookup_parser.parse_args()
        include_actors = args.pop('include_actors')
        include_translations = args.pop('include_translations')
        kwargs = args
        kwargs['title'] = title
        try:
            series = at.lookup_series(session=session, **kwargs)
        except LookupError as e:
            raise NotFoundError(e.args[0])
        result = series.to_dict()
        if include_actors:
            result['actors'] = list_actors(series.actors)
        if include_translations:
            result['translations'] = get_translations_dict(series.translations, 'show')
        return jsonify(result)


@trakt_api.route('/movies/<string:title>/')
@api.doc(params={'title': 'Movie name'})
class TraktMovieSearchApi(APIResource):
    @etag(cache_age=3600)
    @api.response(200, 'Successfully found show', movie_return_schema)
    @api.response(NotFoundError)
    @api.doc(parser=lookup_parser)
    def get(self, title, session=None):
        """Trakt movie lookup"""
        args = lookup_parser.parse_args()
        include_actors = args.pop('include_actors')
        include_translations = args.pop('include_translations')
        kwargs = args
        kwargs['title'] = title
        try:
            movie = at.lookup_movie(session=session, **kwargs)
        except LookupError as e:
            raise NotFoundError(e.args[0])
        result = movie.to_dict()
        if include_actors:
            result['actors'] = list_actors(movie.actors)
        if include_translations:
            result['translations'] = get_translations_dict(movie.translations, 'movie')
        return jsonify(result)
