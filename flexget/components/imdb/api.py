from flask import jsonify

from flexget.api import APIResource, api
from flexget.api.app import etag
from flexget.components.imdb.utils import ImdbSearch

imdb_api = api.namespace('imdb', description='IMDB lookup endpoint')


class ObjectsContainer:
    movie_object = {
        'type': 'object',
        'properties': {
            'imdb_id': {'type': 'string'},
            'match': {'type': 'number'},
            'name': {'type': 'string'},
            'url': {'type': 'string'},
            'year': {'type': 'number'},
            'thumbnail': {'type': 'string'},
        },
        'required': ['imdb_id', 'match', 'name', 'url', 'year'],
        'additionalProperties': False,
    }

    return_object = {'type': 'array', 'items': movie_object}


return_schema = api.schema_model('imdb_search_schema', ObjectsContainer.return_object)


@imdb_api.route('/search/<string:title>/')
@api.doc(params={'title': 'Movie name or IMDB ID'})
class IMDBMovieSearch(APIResource):
    # noinspection PyUnusedLocal
    @etag
    @api.response(200, model=return_schema)
    def get(self, title, session=None):
        """Get a list of IMDB search result by name or ID"""
        raw_movies = ImdbSearch().smart_match(title, single_match=False)
        if not raw_movies:
            return jsonify([])
        # Convert single movie to list to preserve consistent reply
        if not isinstance(raw_movies, list):
            raw_movies = [raw_movies]
        return jsonify(raw_movies)
