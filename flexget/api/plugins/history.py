from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from math import ceil

from flask import jsonify
from sqlalchemy import desc, asc

from flexget.api import api, APIResource
from flexget.api.app import BadRequest, etag, link_header, pagination_parser
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
        }
    }

    history_list_object = {'type': 'array', 'items': base_history_object}


history_list_schema = api.schema('history.list', ObjectsContainer.history_list_object)

sort_choices = ('id', 'task', 'filename', 'url', 'title', 'time', 'details')

# Create pagination parser
history_parser = pagination_parser(sort_choices=sort_choices, default='time')
history_parser.add_argument('task', help='Filter by task name')


@history_api.route('/')
@api.doc(parser=history_parser)
class HistoryAPI(APIResource):
    @etag
    @api.response(BadRequest)
    @api.response(200, model=history_list_schema)
    def get(self, session=None):
        """ List of previously accepted entries """
        args = history_parser.parse_args()

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        # Filter param
        task = args['task']

        # Build query count
        count_query = session.query(History)
        if task:
            count_query = count_query.filter(History.task == task)
        count = count_query.count()

        if not count:
            return jsonify([])

        pages = int(ceil(count / float(per_page)))

        if page > pages:
            raise BadRequest('page %s does not exist' % page)

        start = (page - 1) * per_page
        finish = start + per_page

        # Choose sorting order
        if sort_order == 'desc':
            order = desc
        else:
            order = asc

        # Build item query
        items = session.query(History)
        if task:
            items = items.filter(History.task == task)
        items = items.order_by(order(getattr(History, sort_by))).slice(start, finish)

        # Create Link header
        full_url = self.api.base_url + history_api.path
        link = link_header(full_url, page, per_page, pages)

        # Create response
        rsp = jsonify([item.to_dict() for item in items])

        # Add link header to response
        rsp.headers.extend(link)
        return rsp
