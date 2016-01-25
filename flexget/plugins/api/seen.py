from __future__ import unicode_literals, division, absolute_import

from math import ceil
from operator import itemgetter
from urllib import unquote

from flask_restplus import inputs

from flexget.api import api, APIResource, jsonify, request
from flexget.plugins.filter import seen
from flexget.utils.imdb import is_imdb_url, extract_id


def return_imdb_id(value):
    if is_imdb_url(value):
        imdb_id = extract_id(value)
        if imdb_id:
            value = imdb_id
    return value


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
seen_object_schema = api.schema('seen_object_schema', seen_object)

seen_object_input_schema = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'reason': {'type': 'string'},
        'task': {'type': 'string'},
        'local': {'type': 'boolean', 'default': False},
        'fields': {'type': 'object'}
    },
    'required': ['title', 'fields', 'task'],
    'additional_properties': False
}
seen_object_input_schema = api.schema('seen_object_input_schema', seen_object_input_schema)

seen_search_schema = {
    'type': 'object',
    'properties': {
        'seen_entries': {
            'type': 'array',
            'items': seen_object
        },
        'number_of_seen_entries': {'type': 'integer'},
        'total_number_of_pages': {'type': 'integer'},
        'page_number': {'type': 'integer'}
    }
}
seen_search_schema = api.schema('seen_search_schema', seen_search_schema)


def seen_search_local_status_enum(value):
    try:
        return inputs.boolean(value)
    except ValueError:
        if value != 'all':
            raise ValueError('Invalid value received')
        return value


seen_search_sort_enum_list = ['title', 'task', 'added', 'local', 'id']


def seen_search_sort_enum(value):
    enum = seen_search_sort_enum_list
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    return value


def seen_search_sort_order_enum(value):
    enum = ['desc', 'asc']
    if isinstance(value, bool):
        return value
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    if value == 'desc':
        return True
    return False


seen_search_parser = api.parser()
seen_search_parser.add_argument('value', help='Search by any field value or leave empty to get entries')
seen_search_parser.add_argument('page', type=int, default=1, help='Page number')
seen_search_parser.add_argument('max', type=int, default=100, help='Seen entries per page')
seen_search_parser.add_argument('local_seen', type=seen_search_local_status_enum, default='all',
                                help='Filter list by local status. Filter by true, false or all. Default is all')
seen_search_parser.add_argument('sort_by', type=seen_search_sort_enum, default='added',
                                help="Sort response by {0}".format(' ,'.join(seen_search_sort_enum_list)))
seen_search_parser.add_argument('order', type=seen_search_sort_order_enum, default='desc',
                                help='Sorting order. Can be asc or desc. Default is desc')


@seen_api.route('/')
class SeenSearchAPI(APIResource):
    @api.response(404, 'Page does not exist')
    @api.response(200, 'Successfully retrieved seen objects', seen_search_schema)
    @api.doc(parser=seen_search_parser)
    def get(self, session):
        """ Search for seen entries """
        args = seen_search_parser.parse_args()
        value = args['value']
        page = args['page']
        max_results = args['max']
        status = args['local_seen']
        sort_by = args['sort_by']
        order = args['order']
        # Handles default if it explicitly called
        if order == 'desc':
            order = True

        if value:
            value = unquote(value)
            value = '%' + value + '%'
        seen_entries_list = seen.search(value, status, session)
        count = len(seen_entries_list)

        pages = int(ceil(count / float(max_results)))
        seen_entries = []
        if page > pages and pages != 0:
            return {'error': 'page %s does not exist' % page}, 404

        start = (page - 1) * max_results
        finish = start + max_results
        if finish > count:
            finish = count

        for seen_entry_num in range(start, finish):
            seen_entries.append(seen_entries_list[seen_entry_num].to_dict())

        sorted_seen_entries_list = sorted(seen_entries, key=itemgetter(sort_by), reverse=order)

        return jsonify({
            'seen_entries': sorted_seen_entries_list,
            'number_of_seen_entries': count,
            'page_number': page,
            'total_number_of_pages': pages
        })

    @api.response(400, 'A matching seen object is already added')
    @api.response(200, 'Successfully added new seen object', seen_object_schema)
    @api.validate(seen_object_input_schema)
    def post(self, session):
        """ Manually add entries to seen plugin """
        data = request.json
        kwargs = {
            'title': data.get('title'),
            'task_name': 'seen_API',
            'fields': data.get('fields'),
            'reason': data.get('reason'),
            'local': data.get('local', False),
            'session': session
        }
        values = [value for value in kwargs['fields'].values()]
        exist = seen.search_by_field_values(field_value_list=values, task_name='seen_API', local=kwargs['local'],
                                            session=session)
        if exist:
            return {'status': 'error',
                    'message': "Seen entry matching the value '{0}' is already added".format(exist.value)}, 400

        seen_entry = seen.add(**kwargs)
        return jsonify({
            'status': 'success',
            'message': 'successfully added seen object',
            'seen_object': seen_entry
        })
