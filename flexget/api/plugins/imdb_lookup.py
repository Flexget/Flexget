from __future__ import unicode_literals, division, absolute_import

from flask import jsonify

from flexget.api import api, APIResource
from flexget.api.app import etag
from flexget.utils.imdb import ImdbSearch

imdb_api = api.namespace('imdb', description='IMDB lookup endpoint')


class ObjectsContainer(object):
    movie_object = {
        'type': 'object',
        'properties': {
            'imdb_id': {'type': 'string'},
            'match': {'type': 'number'},
            'name': {'type': 'string'},
            'url': {'type': 'string'},
            'year': {'type': 'string'},
            'thumbnail': {'type': 'string'}
        },
        'required': ['imdb_id', 'match', 'name', 'url', 'year'],
        'additionalProperties': False
    }

    return_object = {'type': 'array', 'items': movie_object}


return_schema = api.schema_model('imdb_search_schema', ObjectsContainer.return_object)


@imdb_api.route('/search/<string:title>/')
@api.doc(params={'title': 'Movie name or IMDB ID'})
class IMDBMovieSearch(APIResource):
    @etag
    @api.response(200, model=return_schema)
    def get(self, title, session=None):
        """ Get a list of IMDB search result by name or ID"""
        raw_movies = ImdbSearch().smart_match(title, single_match=False)
        if not raw_movies:
            return jsonify([])
        # Convert single movie to list to preserve consistent reply
        if not isinstance(raw_movies, list):
            raw_movies = [raw_movies]
        return jsonify(raw_movies)
