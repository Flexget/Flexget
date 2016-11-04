from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from flexget.plugins.filter.seen import forget_by_id
from future.moves.urllib.parse import unquote

from math import ceil
from sqlalchemy.orm.exc import NoResultFound
from flask import jsonify, request
from flask_restplus import inputs

from flexget.api import api, APIResource
from flexget.api.app import NotFoundError, base_message_schema, success_response, etag, pagination_headers
from flexget.plugins.filter import seen

seen_api = api.namespace('seen', description='Managed Flexget seen entries and fields')


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

    seen_search_object = {'type': 'array', 'items': seen_object}


seen_object_schema = api.schema('seen_object_schema', ObjectsContainer.seen_object)
seen_search_schema = api.schema('seen_search_schema', ObjectsContainer.seen_search_object)

seen_base_parser = api.parser()
seen_base_parser.add_argument('value', help='Filter by any field value or leave empty to get all entries')
seen_base_parser.add_argument('local', type=inputs.boolean, default=None,
                              help='Filter results by seen locality.')

sort_choices = ('title', 'task', 'added', 'local', 'reason', 'id')
seen_search_parser = api.pagination_parser(seen_base_parser, sort_choices)


@seen_api.route('/')
class SeenSearchAPI(APIResource):
    @etag
    @api.response(NotFoundError)
    @api.response(200, 'Successfully retrieved seen objects', seen_search_schema)
    @api.doc(parser=seen_search_parser, description='Get seen entries')
    def get(self, session):
        """ Search for seen entries """
        args = seen_search_parser.parse_args()

        # Filter params
        value = args['value']
        local = args['local']

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        descending = sort_order == 'desc'

        # Unquotes and prepares value for DB lookup
        if value:
            value = unquote(value)
            value = '%{0}%'.format(value)

        start = per_page * (page - 1)
        stop = start + per_page

        kwargs = {
            'value': value,
            'status': local,
            'stop': stop,
            'start': start,
            'order_by': sort_by,
            'descending': descending,
            'session': session
        }

        total_items = seen.search(count=True, **kwargs)

        if not total_items:
            return jsonify([])

        raw_seen_entries_list = seen.search(**kwargs).all()

        converted_seen_entry_list = [entry.to_dict() for entry in raw_seen_entries_list]

        # Total number of pages
        total_pages = int(ceil(total_items / float(per_page)))

        # Actual results in page
        actual_size = min(len(converted_seen_entry_list), per_page)

        # Invalid page request
        if page > total_pages and total_pages != 0:
            raise NotFoundError('page %s does not exist' % page)

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Create response
        rsp = jsonify(converted_seen_entry_list)

        # Add link header to response
        rsp.headers.extend(pagination)
        return rsp

    @api.response(200, 'Successfully delete all entries', model=base_message_schema)
    @api.doc(parser=seen_base_parser, description='Delete seen entries')
    def delete(self, session):
        """ Delete seen entries """
        args = seen_base_parser.parse_args()
        value = args['value']
        local = args['local']

        if value:
            value = unquote(value)
            value = '%' + value + '%'
        seen_entries_list = seen.search(value=value, status=local, session=session)

        deleted = 0
        for se in seen_entries_list:
            forget_by_id(se.id, session=session)
            deleted += 1
        return success_response('successfully deleted %i entries' % deleted)


@seen_api.route('/<int:seen_entry_id>/')
@api.doc(params={'seen_entry_id': 'ID of seen entry'})
@api.response(NotFoundError)
class SeenSearchIDAPI(APIResource):
    @etag
    @api.response(200, model=seen_object_schema)
    def get(self, seen_entry_id, session):
        """ Get seen entry by ID """
        try:
            seen_entry = seen.get_entry_by_id(seen_entry_id, session=session)
        except NoResultFound:
            raise NotFoundError('Could not find entry ID {0}'.format(seen_entry_id))
        return jsonify(seen_entry.to_dict())

    @api.response(200, 'Successfully deleted entry', model=base_message_schema)
    def delete(self, seen_entry_id, session):
        """ Delete seen entry by ID """
        try:
            entry = seen.get_entry_by_id(seen_entry_id, session=session)
        except NoResultFound:
            raise NotFoundError('Could not delete entry ID {0}'.format(seen_entry_id))
        forget_by_id(entry.id, session=session)
        return success_response('successfully deleted seen entry {}'.format(seen_entry_id))
