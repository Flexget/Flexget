from __future__ import unicode_literals, division, absolute_import

import logging
from flask import jsonify, request
from flexget.api import api, APIResource
from flexget.entry import Entry
from flexget.plugins.api.movie_queue import empty_response
from flexget.plugins.list.movie_list import PluginMovieList as ml

log = logging.getLogger('movie_list')

movie_list_api = api.namespace('movie_list', description='Movie List operations')

base_movie_entry = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'url': {'type': 'string'},
        'movie_name': {'type': 'string'},
        'movie_year': {'type': 'integer'},
        'list_name': {'type': 'string'}
    },
    'additionalProperties': True,
    'allOf': [
        {'required': ['url']},
        {'oneOf': [
            {'required': ['title']},
            {'required': ['movie_name', 'movie_year']}
        ]},
    ]
}

movie_list_return_model = {
   'type': 'object',
    'properties': {
        'entries': {'type': 'array', 'items': base_movie_entry},
        'number_of_entries': {'type': 'integer'},
        'list_name': {'type': 'string'}
    }
}

base_movie_entry = api.schema('base_movie_entry', base_movie_entry)
movie_list_return_model = api.schema('movie_list_return_model', movie_list_return_model)

@movie_list_api.route('/<string:list_name>')
@api.doc(params={'list_name': 'Name of the list'})
class MovieListAPI(APIResource):
    @api.response(200, model=movie_list_return_model)
    def get(self, list_name, session=None):
        ''' Get Movie list entries '''
        # TODO Pagination
        movies = [entry.to_dict() for entry in ml.get_list(list_name)]
        return jsonify({'entries': movies,
                        'number_of_entries': len(movies),
                        'list_name': list_name})

    @api.validate(base_movie_entry)
    @api.response(201, model=base_movie_entry)
    @api.doc(description="This will create a new list if list name doesn't exist")
    def post(self, list_name, session=None):
        ''' Adds a movie to the list. '''
        data = request.json
        movies = ml.get_list(list_name)
        # TODO This could be a param but i don't think it matters that much
        data['accepted_by'] = data['task'] = 'FlexGet API'

        movies.add(data, session=session)
        return Entry(data).to_dict(), 201

    @api.validate(base_movie_entry)
    @api.response(200, model=empty_response)
    def delete(self, list_name, session=None):
        ''' Remove an movie from the list '''
        data = request.json
        entries = ml.get_list(list_name)
        entries.discard(data)
        return {}
