from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from flexget.plugins.filter.seen import forget_by_id
from future.moves.urllib.parse import unquote

import copy
from math import ceil
from sqlalchemy.orm.exc import NoResultFound
from flask import jsonify, request
from flask_restplus import inputs

from flexget.api import api, APIResource, NotFoundError, CannotAddResource, success_schema, success_response, APIError
from flexget.plugins.filter import seen

seen_api = api.namespace('seen', description='Managed Flexget seen entries and fields')

PLUGIN_TASK_NAME = 'seen_plugin_API'  # Name of task to use when adding entries via API


class ObjectsContainer(object):
    seen_field_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'field': {'type': 'string'},
            'value': {'type': 'string'},
            'added': {'type': 'string', 'format': 'date-time'},
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
            'added': {'type': 'string', 'format': 'date-time'},
            'local': {'type': 'boolean'},
            'fields': {'type': 'array', 'items': seen_field_object}
        }
    }
    seen_object_schema = api.schema('seen_object_schema', seen_object)

    # Copy inout schema from seen object and manipulate to get desired fields
    seen_object_input_schema = copy.deepcopy(seen_object)

    # Removing unneeded fields
    del seen_object_input_schema['properties']['id']
    del seen_object_input_schema['properties']['added']

    # Get dict and not array of dicts
    seen_object_input_schema['properties']['fields'] = {'type': 'object'}

    # Set default local status to False
    seen_object_input_schema['properties']['local'] = {'type': 'boolean', 'default': False}

    # Add JSON schema validation fields
    seen_object_input_schema.update({'required': ['title', 'fields'],
                                     'additional_properties': False})

    seen_object_input_schema = api.schema('seen_object_input_schema', seen_object_input_schema)

    seen_search_schema = {
        'type': 'object',
        'properties': {
            'seen_entries': {
                'type': 'array',
                'items': seen_object
            },
            'total_number_of_seen_entries': {'type': 'integer'},
            'number_of_seen_entries': {'type': 'integer'},
            'total_number_of_pages': {'type': 'integer'},
            'page_number': {'type': 'integer'}
        }
    }
    seen_search_schema = api.schema('seen_search_schema', seen_search_schema)


seen_search_parser = api.parser()
seen_search_parser.add_argument('value', help='Search by any field value or leave empty to get entries')
seen_search_parser.add_argument('page', type=int, default=1, help='Page number')
seen_search_parser.add_argument('page_size', type=int, default=10, help='Seen entries per page. Max value is 100')
seen_search_parser.add_argument('is_seen_local', type=inputs.boolean, default=None,
                                help='Filter results by seen locality.')
seen_search_parser.add_argument('sort_by', choices=('title', 'task', 'added', 'local', 'id'), default='added',
                                help="Sort response by attribute")
seen_search_parser.add_argument('order', choices=('asc', 'desc'), default='desc', help='Sorting order.')

seen_delete_parser = api.parser()
seen_delete_parser.add_argument('value', help='Delete by value or leave empty to delete all. BE CAREFUL WITH THIS')
seen_delete_parser.add_argument('is_seen_local', type=inputs.boolean, default=None,
                                help='Filter results by seen locality.')


@seen_api.route('/')
class SeenSearchAPI(APIResource):
    @api.response(NotFoundError)
    @api.response(200, 'Successfully retrieved seen objects', ObjectsContainer.seen_search_schema)
    @api.doc(parser=seen_search_parser, description='Get seen entries')
    def get(self, session):
        """ Search for seen entries """
        args = seen_search_parser.parse_args()
        value = args['value']
        page = args['page']
        page_size = args['page_size']
        is_seen_local = args['is_seen_local']
        sort_by = args['sort_by']
        order = args['order']

        # Handle max size limit
        if page_size > 100:
            page_size = 100

        # Handles default if it explicitly called
        descending = bool(order == 'desc')

        # Unquotes and prepares value for DB lookup
        if value:
            value = unquote(value)
            value = '%{0}%'.format(value)

        start = page_size * (page - 1)
        stop = start + page_size

        kwargs = {
            'value': value,
            'status': is_seen_local,
            'stop': stop,
            'start': start,
            'order_by': sort_by,
            'descending': descending,
            'session': session
        }
        count = seen.search(count=True, **kwargs)

        raw_seen_entries_list = seen.search(**kwargs)
        converted_seen_entry_list = [entry.to_dict() for entry in raw_seen_entries_list.all()]

        pages = int(ceil(count / float(page_size)))

        actual_size = min(count, page_size)

        # Invalid page request
        if page > pages and pages != 0:
            raise NotFoundError('page %s does not exist' % page)

        return jsonify({
            'seen_entries': converted_seen_entry_list,
            'total_number_of_seen_entries': count,
            'page_size': actual_size,
            'page_number': page,
            'total_number_of_pages': pages
        })

    example = "fields: {'url': 'http://123.com', 'title': 'A.Torrent', 'imdb_id': 'tt1234567'"

    @api.response(CannotAddResource)
    @api.response(201, 'Successfully added new seen object', ObjectsContainer.seen_object_schema)
    @api.validate(model=ObjectsContainer.seen_object_input_schema,
                  description='Fields attribute takes a dict to add as seen entry fields, '
                              'for example: {0}'.format(example))
    @api.doc(description='Add seen entries')
    def post(self, session):
        """ Manually add entries to seen plugin """
        data = request.json
        kwargs = {
            'title': data.get('title'),
            'task_name': data.get('task', PLUGIN_TASK_NAME),
            'fields': data.get('fields'),
            'reason': data.get('reason'),
            'local': data.get('local', False),
            'session': session
        }
        values = [value for value in list(kwargs['fields'].values())]
        exist = seen.search_by_field_values(field_value_list=values, task_name=PLUGIN_TASK_NAME, local=kwargs['local'],
                                            session=session)
        if exist:
            raise CannotAddResource('Seen entry matching the value \'{0}\' is already added'.format(exist.value))

        seen_entry = seen.add(**kwargs)
        reply = jsonify(seen_entry)
        reply.status_code = 201
        return reply

    @api.response(200, 'Successfully delete all entries', model=success_schema)
    @api.doc(parser=seen_delete_parser, description='Delete seen entries')
    def delete(self, session):
        """ Delete seen entries """
        args = seen_delete_parser.parse_args()
        value = args['value']
        is_seen_local = args['is_seen_local']

        if value:
            value = unquote(value)
            value = '%' + value + '%'
        seen_entries_list = seen.search(value=value, status=is_seen_local, session=session)

        deleted = 0
        for se in seen_entries_list:
            try:
                forget_by_id(se.id, session=session)
            except NoResultFound:
                raise APIError('Error, could not delete seen entry with id {}'.format(se.id))
        return success_response('successfully deleted %i entries' % deleted)


@seen_api.route('/<int:seen_entry_id>/')
@api.doc(params={'seen_entry_id': 'ID of seen entry'})
@api.response(NotFoundError)
class SeenSearchIDAPI(APIResource):
    @api.response(200, model=ObjectsContainer.seen_object_schema)
    def get(self, seen_entry_id, session):
        """ Get seen entry by ID """
        try:
            seen_entry = seen.get_entry_by_id(seen_entry_id, session=session)
        except NoResultFound:
            raise NotFoundError('Could not find entry ID {0}'.format(seen_entry_id))
        return jsonify(seen_entry.to_dict())

    @api.response(200, 'Successfully deleted entry', model=success_schema)
    def delete(self, seen_entry_id, session):
        """ Delete seen entry by ID """
        try:
            entry = seen.get_entry_by_id(seen_entry_id, session=session)
        except NoResultFound:
            raise NotFoundError('Could not delete entry ID {0}'.format(seen_entry_id))
        entry.delete()
        return success_response('successfully deleted seen entry {}'.format(seen_entry_id))
