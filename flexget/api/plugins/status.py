from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import argparse
import cgi
import copy
from datetime import datetime, timedelta
from json import JSONEncoder

from flask import jsonify, Response, request
from flask_restplus import inputs
from flexget.api.core.tasks import tasks_api
from flexget.plugins.operate.status import StatusTask, TaskExecution
from queue import Queue, Empty

from flexget.api import api, APIResource
from flexget.api.app import APIError, NotFoundError, Conflict, BadRequest, success_response, \
    base_message_schema, etag
from flexget.config_schema import process_config
from flexget.entry import Entry
from flexget.event import event
from flexget.options import get_parser
from flexget.task import task_phases
from flexget.utils import json
from flexget.utils import requests
from flexget.utils.lazy_dict import LazyLookup

status_api = api.namespace('status', description='View and manage task execution status')


class ObjectsContainer(object):
    task_status_execute_schema = {
        'type': 'object',
        'properties': {
            'abort_reason': {'type': ['string', 'null']},
            'accepted': {'type': 'integer'},
            'end': {'type': 'string', 'format': 'date-time'},
            'failed': {'type': 'integer'},
            'id': {'type': 'integer'},
            'produced': {'type': 'integer'},
            'rejected': {'type': 'integer'},
            'start': {'type': 'string', 'format': 'date-time'},
            'succeeded': {'type': 'boolean'},
            'task_id': {'type': 'integer'}
        },
        'required': ['abort_reason', 'accepted', 'end', 'failed', 'id', 'produced', 'rejected', 'start', 'succeeded',
                     'task_id'],
        'additionalProperties': False
    }

    task_status_schema = {
        'type': 'object',
        'properties': {
            'executions': {'type': 'array', 'items': task_status_execute_schema},
            'id': {'type': 'integer'},
            'name': {'type': 'string'},
            'total_executions': {'type': 'integer'}
        },
        'required': ['executions', 'id', 'name', 'total_executions'],
        'additionalProperties': False
    }

    task_status_list_schema = {'type': 'array', 'items': task_status_schema}


task_status_list = api.schema('tasks.tasks_status_list', ObjectsContainer.task_status_list_schema)

default_start_date = (datetime.now() - timedelta(weeks=1)).strftime('%Y-%m-%d')

status_parser = api.parser()
status_parser.add_argument('succeeded', type=inputs.boolean, default=True, help='Filter by success status')
status_parser.add_argument('produced', type=inputs.boolean, default=True, store_missing=False,
                           help='Filter by tasks that produced entries')
status_parser.add_argument('start_date', type=inputs.datetime_from_iso8601, default=default_start_date,
                           help='Filter by minimal start date. Example: \'2012-01-01\'')
status_parser.add_argument('end_date', type=inputs.datetime_from_iso8601,
                           help='Filter by maximal end date. Example: \'2012-01-01\'')
status_parser.add_argument('limit', default=100, type=int,
                           help='Limit return of executions per task, as that number can be huge')


@tasks_api.route('/status/')
@status_api.route('/')
@api.doc(parser=status_parser)
class TaskStatusAPI(APIResource):
    @api.response(200, model=task_status_list)
    def get(self, session=None):
        """Get tasks execution status"""
        args = status_parser.parse_args()
        succeeded = args.get('succeeded')
        produced = args.get('produced')
        start_date = args.get('start_date')
        end_date = args.get('end_date')
        limit = args.get('limit')

        if limit > 1000:
            limit = 1000

        status_tasks = []
        for task in session.query(StatusTask).all():
            status_task = task.to_dict()
            status_task['total_executions'] = task.executions.count()
            executions = task.executions.filter(TaskExecution.succeeded == succeeded)
            if produced is True:
                executions = executions.filter(TaskExecution.produced > 1)
            if start_date:
                executions = executions.filter(TaskExecution.start >= start_date)
            if end_date:
                executions = executions.filter(TaskExecution.start <= end_date)
            executions = executions.order_by(TaskExecution.start.desc()).limit(limit)
            status_task['executions'] = [e.to_dict() for e in executions.all()]
            status_tasks.append(status_task)
        return jsonify(status_tasks)
