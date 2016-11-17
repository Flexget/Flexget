from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from math import ceil

from flask import jsonify, request
from flask_restplus import inputs
from flexget.plugins.filter.pending_approval import list_pending_entries, PendingEntry

from flexget.api import api, APIResource
from flexget.api.app import base_message_schema, success_response, NotFoundError, etag, pagination_headers

pending_api = api.namespace('pending', description='View and manage pending entries')


class ObjectsContainer(object):
    pending_entry_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'task_name': {'type': 'string'},
            'title': {'type': 'string'},
            'url': {'type': 'string'},
            'approved': {'type': 'boolean'},
            'added': {'type': 'string', 'format': 'date-time'}
        }
    }

    pending_entry_list = {'type': 'array', 'items': pending_entry_object}


pending_entry_schema = api.schema('pending.entry', ObjectsContainer.pending_entry_object)
pending_entry_list_schema = api.schema('pending.entry_list', ObjectsContainer.pending_entry_list)

sort_choices = ('added', 'task_name', 'title', 'url', 'approved')
pending_parser = api.pagination_parser(sort_choices=sort_choices)
pending_parser.add_argument('task_name', help='Filter by task name')
pending_parser.add_argument('approved', type=inputs.boolean, help='Filter by approval status')


@pending_api.route('/')
@api.response(NotFoundError)
@api.response(200, model=pending_entry_list_schema)
@api.doc(parser=pending_parser)
class PendingEntriesAPI(APIResource):
    @etag
    def get(self, session=None):
        """List all pending entries"""
        args = pending_parser.parse_args()

        # Filter params
        task_name = args.get('task_name')
        approved = args.get('approved')

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        descending = sort_order == 'desc'

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        start = per_page * (page - 1)
        stop = start + per_page

        kwargs = {
            'task_name': task_name,
            'approved': approved,
            'start': start,
            'stop': stop,
            'descending': descending,
            'sort_by': sort_by,
            'session': session
        }

        total_items = session.query(PendingEntry).count()

        if not total_items:
            return jsonify([])

        pending_entries = [pending.to_dict() for pending in list_pending_entries(**kwargs)]

        total_pages = int(ceil(total_items / float(per_page)))

        if page > total_pages:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(per_page, len(pending_entries))

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Created response
        rsp = jsonify(pending_entries)

        # Add link header to response
        rsp.headers.extend(pagination)

        return rsp
