from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from math import ceil

from flask import jsonify
from sqlalchemy import desc

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

history_parser = pagination_parser.copy()
history_parser.add_argument('task', type=str, required=False, default=None, help='Filter by task name')


@history_api.route('/')
@api.doc(parser=history_parser)
class HistoryAPI(APIResource):
    @etag
    @api.response(BadRequest)
    @api.response(200, model=history_list_schema)
    def get(self, session=None):
        """ List of previously accepted entries """
        args = history_parser.parse_args()
        page = args['page']
        per_page = args['per_page']
        task = args['task']

        count_query = session.query(History)
        if task:
            count_query = count_query.filter(History.task == task)
        count = count_query.count()

        pages = int(ceil(count / float(per_page)))

        if not count:
            return jsonify([])

        if page > pages:
            raise BadRequest('page %s does not exist' % page)

        start = (page - 1) * per_page
        finish = start + per_page

        items = session.query(History)
        if task:
            items = items.filter(History.task == task).order_by(desc(History.time)).slice(start, finish)
        items = items.order_by(desc(History.time)).slice(start, finish)

        full_url = self.api.base_url + history_api.path

        link = link_header(full_url, page, per_page, pages)
        rsp = jsonify([item.to_dict() for item in items])
        rsp.headers.extend(link)
        return rsp
