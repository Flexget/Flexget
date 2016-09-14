from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from math import ceil

from flask import jsonify
from sqlalchemy import desc

from flexget.api.app import api
from flexget.api.responses import BadRequest
from flexget.api.models import APIResource
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

    history_list_object = {
        'type': 'object',
        'properties': {
            'entries': {'type': 'array', 'items': base_history_object},
            'pages': {'type': 'integer'}
        }
    }


history_list_schema = api.schema('history.list', ObjectsContainer.history_list_object)

history_parser = api.parser()
history_parser.add_argument('page', type=int, required=False, default=1, help='Page number')
history_parser.add_argument('max', type=int, required=False, default=50, help='Results per page')
history_parser.add_argument('task', type=str, required=False, default=None, help='Filter by task name')


@history_api.route('/')
@api.doc(parser=history_parser)
class HistoryAPI(APIResource):
    @api.response(BadRequest)
    @api.response(200, model=history_list_schema)
    def get(self, session=None):
        """ List of previously accepted entries """
        args = history_parser.parse_args()
        page = args['page']
        max_results = args['max']
        task = args['task']

        if task:
            count = session.query(History).filter(History.task == task).count()
        else:
            count = session.query(History).count()

        if not count:
            return {'entries': [], 'pages': 0}

        pages = int(ceil(count / float(max_results)))

        if page > pages:
            raise BadRequest('page %s does not exist' % page)

        start = (page - 1) * max_results
        finish = start + max_results

        if task:
            items = session.query(History).filter(History.task == task).order_by(desc(History.time)).slice(start,
                                                                                                           finish)
        else:
            items = session.query(History).order_by(desc(History.time)).slice(start, finish)

        return jsonify({
            'entries': [item.to_dict() for item in items],
            'pages': pages
        })
