from __future__ import unicode_literals, division, absolute_import

from flexget.api import api, APIResource, jsonify
from flexget.plugins.filter import seen

seen_api = api.namespace('seen', description='Managed Flexget seen entries and fields')

seen_field_object = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'field': {'type': 'string'},
        'value': {'type': 'string'},
        'added': {'type': 'string'},
        'seen_entry_id': {'type': 'integer'}
    }
}

seen_object = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'title': {'type': 'string'},
        'reason': {'type': 'string'},
        'task': {'type': 'string'},
        'added': {'type': 'string'},
        'local': {'type': 'string'},
        'fields': {'type': 'array', 'items': seen_field_object}
    }
}

seen_search_schema = {
    'type': 'object',
    'properties': {
        'seen_entries': {
            'type': 'array',
            'items': seen_object
        },
        'number_of_seen_entries': {'type': 'integer'}
    }
}
seen_search_schema = api.schema('seen_search_schema', seen_search_schema)


def get_seen_entry_details(seen_entry):
    fields = []
    for field in seen_entry.fields:
        field_object = {
            'field': field.field,
            'id': field.id,
            'value': field.value,
            'added': field.added,
            'seen_entry_id': field.seen_entry_id
        }
        fields.append(field_object)

    seen_entry_object = {
        'id': seen_entry.id,
        'title': seen_entry.title,
        'reason': seen_entry.reason,
        'task': seen_entry.task,
        'added': seen_entry.added,
        'local': seen_entry.local,
        'fields': fields
    }
    return seen_entry_object


@seen_api.route('/<string:value>')
class SeenAPI(APIResource):
    @api.response(200, 'Successfully retrieved seen objects', seen_search_schema)
    def get(self, value, session):
        """ Search for seen entries """
        value = '%' + value + '%'
        seen_entries_list = seen.search(value, session)

        seen_entries = []

        for seen_entry in seen_entries_list:
            seen_entries.append(get_seen_entry_details(seen_entry))

        return jsonify({
            'seen_entries': seen_entries,
            'number_of_seen_entries': len(seen_entries)
        })
