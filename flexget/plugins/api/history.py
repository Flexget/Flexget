from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from math import ceil

from flask import jsonify
from sqlalchemy import desc

from flexget.api import api, APIResource
from flexget.plugins.output.history import History

log = logging.getLogger('history')

history_api = api.namespace('history', description='Entry History')

history_api_schema = {
    'type': 'object',
    'properties': {
        'entries': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'details': {'type': 'string'},
                    'filename': {'type': 'string'},
                    'id': {'type': 'integer'},
                    'task': {'type': 'string'},
                    'time': {'type': 'string'},
                    'title': {'type': 'string'},
                    'url': {'type': 'string'}
                }
            }
        },
        'pages': {'type': 'integer'}
    }
}

history_api_schema = api.schema('history.list', history_api_schema)

default_error_schema = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'}
    }
}

default_error_schema = api.schema('default_error_schema', default_error_schema)

history_parser = api.parser()
history_parser.add_argument('page', type=int, required=False, default=1, help='Page number')
history_parser.add_argument('max', type=int, required=False, default=50, help='Results per page')
history_parser.add_argument('task', type=str, required=False, default=None, help='Filter by task name')


@history_api.route('/')
@api.doc(parser=history_parser)
class HistoryAPI(APIResource):

    @api.response(404, description='Page does not exist', model=default_error_schema)
    @api.response(200, model=history_api_schema)
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
            return {'error': 'page %s does not exist' % page}, 404

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
