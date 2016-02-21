from __future__ import unicode_literals, division, absolute_import

import copy
import logging

from flask import jsonify, request

from flexget.api import api, APIResource
from flexget.entry import Entry
from flexget.plugins.api.seen import empty_response
from flexget.plugins.list.entry_list import EntryList as el

log = logging.getLogger('entry_list')

entry_list_api = api.namespace('entry_list', description='Entry List operations')

base_entry_model = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'url': {'type': 'string'}
    },
    'additionalProperties': True,
    'required': ['title', 'url']
}

entry_return_model = copy.deepcopy(base_entry_model)
entry_return_model['properties']['task'] = {'type': 'string'}
entry_return_model['properties']['accepted_by'] = {'type': 'string'}
entry_return_model['properties']['original_url'] = {'type': 'string'}

base_entry_model = api.schema('base_entry_model', base_entry_model)
entry_return_model = api.schema('entry_return_model', entry_return_model)

entry_list_return_model = {
    'type': 'object',
    'properties': {
        'entries': {'type': 'array', 'items': entry_return_model},
        'number_of_entries': {'type': 'integer'},
        'list_name': {'type': 'string'}
    }
}

entry_list_return_model = api.schema('entry_list_return_model', entry_list_return_model)


@entry_list_api.route('/<string:list_name>')
@api.doc(params={'list_name': 'Name of the list'})
class EntryListAPI(APIResource):
    @api.response(200, model=entry_list_return_model)
    def get(self, list_name, session=None):
        ''' Get Entry list entries '''
        entries = [entry.to_dict() for entry in el.get_list(list_name)]
        return jsonify({'entries': entries,
                        'number_of_entries': len(entries),
                        'list_name': list_name})

    @api.validate(base_entry_model)
    @api.response(201, model=entry_return_model)
    def post(self, list_name, session=None):
        ''' Adds an entry to the list '''
        data = request.json
        entries = el.get_list(list_name)
        # TODO This could be a param but i don't think it matters that much
        data['accepted_by'] = data['task'] = 'FlexGet API'

        entries.add(data, session=session)
        return Entry(data).to_dict(), 201

    @api.validate(base_entry_model)
    @api.response(200, model=empty_response)
    def delete(self, list_name, session=None):
        ''' Remove an entry to the list '''
        data = request.json
        entries = el.get_list(list_name)
        entries.discard(data)
