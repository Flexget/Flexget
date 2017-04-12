from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from math import ceil

from flask import jsonify, request
from sqlalchemy import desc, asc

from flexget.api import api, APIResource
from flexget.api.app import BadRequest, etag, pagination_headers, NotFoundError
from flexget.plugins.output.history import History

log = logging.getLogger('history')

history_api = api.namespace('history', description='Entry History')


class ObjectsContainer(object):
    base_history_object = {
        'type': 'object',
        'properties': {
            'details': {'type': 'string'},
            'filename': {'type': 'string'},
            'id': {'type': 'integer'},
            'task': {'type': 'string'},
            'time': {'type': 'string', 'format': 'date-time'},
            'title': {'type': 'string'},
            'url': {'type': 'string'}
        },
        'required': ['details', 'filename', 'id', 'task', 'time', 'title', 'url'],
        'additionalProperties': False
    }

    history_list_object = {'type': 'array', 'items': base_history_object}


history_list_schema = api.schema('history.list', ObjectsContainer.history_list_object)

sort_choices = ('id', 'task', 'filename', 'url', 'title', 'time', 'details')

# Create pagination parser
history_parser = api.pagination_parser(sort_choices=sort_choices, default='time')
history_parser.add_argument('task', help='Filter by task name')


@history_api.route('/')
@api.doc(parser=history_parser)
class HistoryAPI(APIResource):
    @etag
    @api.response(NotFoundError)
    @api.response(200, model=history_list_schema)
    def get(self, session=None):
        """ List of previously accepted entries """
        args = history_parser.parse_args()

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        # Hard limit results per page to 100
        if per_page > 100:
            per_page = 100

        # Filter param
        task = args['task']

        # Build query
        query = session.query(History)
        if task:
            query = query.filter(History.task == task)

        total_items = query.count()

        if not total_items:
            return jsonify([])

        total_pages = int(ceil(total_items / float(per_page)))

        if page > total_pages:
            raise NotFoundError('page %s does not exist' % page)

        start = (page - 1) * per_page
        finish = start + per_page

        # Choose sorting order
        order = desc if sort_order == 'desc' else asc

        # Get items
        try:
            items = query.order_by(order(getattr(History, sort_by))).slice(start, finish)
        except AttributeError as e:
            raise BadRequest(str(e))

        # Actual results in page
        actual_size = min(items.count(), per_page)

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Create response
        rsp = jsonify([item.to_dict() for item in items])

        # Add link header to response
        rsp.headers.extend(pagination)
        return rsp
