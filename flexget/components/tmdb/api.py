from flask import jsonify
from flask_restx import inputs

from flexget import plugin
from flexget.api import APIResource, api
from flexget.api.app import BadRequest, NotFoundError, etag

tmdb_api = api.namespace('tmdb', description='TMDB lookup endpoint')


class ObjectsContainer:
    poster_object = {
        'type': 'object',
        'properties': {
            'id': {'type': ['integer', 'null']},
            'movie_id': {'type': ['integer', 'null']},
            'urls': {'type': 'object'},
            'file_path': {'type': 'string'},
            'width': {'type': 'integer'},
            'height': {'type': 'integer'},
            'aspect_ratio': {'type': 'number'},
            'vote_average': {'type': 'number'},
            'vote_count': {'type': 'integer'},
            'language_code': {'type': ['string', 'null']},
        },
        'required': [
            'id',
            'movie_id',
            'urls',
            'file_path',
            'width',
            'height',
            'aspect_ratio',
            'vote_average',
            'vote_count',
            'language_code',
        ],
        'additionalProperties': False,
    }
    movie_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'imdb_id': {'type': 'string'},
            'name': {'type': 'string'},
            'original_name': {'type': ['string', 'null']},
            'alternative_name': {'type': ['string', 'null']},
            'year': {'type': 'integer'},
            'runtime': {'type': 'integer'},
            'language': {'type': 'string'},
            'overview': {'type': 'string'},
            'tagline': {'type': 'string'},
            'rating': {'type': ['number', 'null']},
            'votes': {'type': ['integer', 'null']},
            'popularity': {'type': ['number', 'null']},
            'adult': {'type': 'boolean'},
            'budget': {'type': ['integer', 'null']},
            'revenue': {'type': ['integer', 'null']},
            'homepage': {'type': ['string', 'null'], 'format': 'uri'},
            'posters': {'type': 'array', 'items': poster_object},
            'backdrops': {'type': 'array', 'items': poster_object},
            'genres': {'type': 'array', 'items': {'type': 'string'}},
            'updated': {'type': 'string', 'format': 'date-time'},
            'lookup_language': {'type': ['string', 'null']},
        },
        'required': [
            'id',
            'name',
            'year',
            'original_name',
            'alternative_name',
            'runtime',
            'language',
            'overview',
            'tagline',
            'rating',
            'votes',
            'popularity',
            'adult',
            'budget',
            'revenue',
            'homepage',
            'genres',
            'updated',
        ],
        'additionalProperties': False,
    }


description = 'Either title, TMDB ID or IMDB ID are required for a lookup'

return_schema = api.schema_model('tmdb_search_schema', ObjectsContainer.movie_object)

tmdb_parser = api.parser()
tmdb_parser.add_argument('title', help='Movie title')
tmdb_parser.add_argument('tmdb_id', help='TMDB ID')
tmdb_parser.add_argument('imdb_id', help='IMDB ID')
tmdb_parser.add_argument('language', help='ISO 639-1 language code')
tmdb_parser.add_argument('year', type=int, help='Movie year')
tmdb_parser.add_argument('only_cached', type=int, help='Return only cached results')
tmdb_parser.add_argument(
    'include_posters', type=inputs.boolean, default=False, help='Include posters in response'
)
tmdb_parser.add_argument(
    'include_backdrops', type=inputs.boolean, default=False, help='Include backdrops in response'
)
tmdb_parser.add_argument(
    'include_backdrops', type=inputs.boolean, default=False, help='Include backdrops in response'
)


@tmdb_api.route('/movies/')
@api.doc(description=description)
class TMDBMoviesAPI(APIResource):
    @etag(cache_age=3600)
    @api.response(200, model=return_schema)
    @api.response(NotFoundError)
    @api.response(BadRequest)
    @api.doc(parser=tmdb_parser)
    def get(self, session=None):
        """ Get TMDB movie data """
        args = tmdb_parser.parse_args()
        title = args.get('title')
        tmdb_id = args.get('tmdb_id')
        imdb_id = args.get('imdb_id')

        posters = args.pop('include_posters', False)
        backdrops = args.pop('include_backdrops', False)

        if not (title or tmdb_id or imdb_id):
            raise BadRequest(description)

        lookup = plugin.get('api_tmdb', 'tmdb.api').lookup

        try:
            movie = lookup(session=session, **args)
        except LookupError as e:
            raise NotFoundError(e.args[0])

        return_movie = movie.to_dict()

        if posters:
            return_movie['posters'] = [p.to_dict() for p in movie.posters]

        if backdrops:
            return_movie['backdrops'] = [p.to_dict() for p in movie.backdrops]

        return jsonify(return_movie)
