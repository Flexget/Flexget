from __future__ import unicode_literals, division, absolute_import

import copy
import logging

from flask import jsonify

from flexget.api import api, APIResource
from flexget.plugins.list.entry_list import EntryList as el

log = logging.getLogger('entry_list')

entry_list_api = api.namespace('entry_list', description='Entry List operations')

base_entry_model = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'url': {'type': 'string'},
        'original_url': {'type': 'string'}
    },
    'additionalProperties': True
}
entry_return_model = copy.deepcopy(base_entry_model)
entry_return_model['properties']['task'] = {'type': 'string'}
entry_return_model['properties']['accepted_by'] = {'type': 'string'}

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
