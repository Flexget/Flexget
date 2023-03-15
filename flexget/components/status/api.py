from datetime import datetime, timedelta
from math import ceil

from flask import jsonify, request
from flask_restx import inputs
from loguru import logger
from sqlalchemy.orm.exc import NoResultFound

from flexget.api.app import APIResource, NotFoundError, api, etag, pagination_headers
from flexget.api.core.tasks import tasks_api

from . import db

logger = logger.bind(name='status_api')

status_api = api.namespace('status', description='View and manage task execution status')


class ObjectsContainer:
    task_status_execution_schema = {
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
            'task_id': {'type': 'integer'},
        },
        'additionalProperties': False,
    }

    executions_list = {'type': 'array', 'items': task_status_execution_schema}

    task_status_schema = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'name': {'type': 'string'},
            'last_execution_time': {'type': ['string', 'null'], 'format': 'date-time'},
            'last_execution': task_status_execution_schema,
        },
        'required': ['id', 'name'],
        'additionalProperties': False,
    }

    task_status_list_schema = {'type': 'array', 'items': task_status_schema}


task_status = api.schema_model('tasks.tasks_status', ObjectsContainer.task_status_schema)
task_status_list = api.schema_model(
    'tasks.tasks_status_list', ObjectsContainer.task_status_list_schema
)
task_executions = api.schema_model('tasks.tasks_executions_list', ObjectsContainer.executions_list)

sort_choices = ('last_execution_time', 'name', 'id')
tasks_parser = api.pagination_parser(sort_choices=sort_choices)
tasks_parser.add_argument(
    'include_execution',
    type=inputs.boolean,
    default=True,
    help='Include the last execution of the task',
)


@tasks_api.route('/status/')
@status_api.route('/')
@api.doc(parser=tasks_parser)
class TasksStatusAPI(APIResource):
    @etag
    @api.response(200, model=task_status_list)
    def get(self, session=None):
        """Get status tasks"""
        args = tasks_parser.parse_args()

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        # Additional data
        include_execution = args.get('include_execution')

        if per_page > 100:
            logger.debug('per_page is higher than max value of 100, setting 100')
            per_page = 100

        start = per_page * (page - 1)
        stop = start + per_page
        descending = sort_order == 'desc'

        kwargs = {
            'start': start,
            'stop': stop,
            'order_by': sort_by,
            'descending': descending,
            'session': session,
        }

        total_items = session.query(db.StatusTask).count()
        logger.debug('db has a total of {} status tasks', total_items)

        if not total_items:
            return jsonify([])

        db_status_tasks = db.get_status_tasks(**kwargs)

        total_pages = int(ceil(total_items / float(per_page)))

        if page > total_pages:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(len(db_status_tasks), per_page)

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        status_tasks = []
        for task in db_status_tasks:
            st_task = task.to_dict()
            if include_execution:
                execution = task.executions.order_by(db.TaskExecution.start.desc()).first()
                st_task['last_execution'] = execution.to_dict() if execution else {}
            status_tasks.append(st_task)

        # Create response
        rsp = jsonify(status_tasks)

        # Add link header to response
        rsp.headers.extend(pagination)
        return rsp


@tasks_api.route('/status/<int:task_id>/')
@status_api.route('/<int:task_id>/')
@api.doc(params={'task_id': 'ID of the status task'}, parser=tasks_parser)
class TaskStatusAPI(APIResource):
    @etag
    @api.response(200, model=task_status)
    @api.response(NotFoundError)
    def get(self, task_id, session=None):
        """Get status task by ID"""
        try:
            task = session.query(db.StatusTask).filter(db.StatusTask.id == task_id).one()
        except NoResultFound:
            raise NotFoundError('task status with id %d not found' % task_id)

        args = tasks_parser.parse_args()
        include_execution = args.get('include_execution')

        st_task = task.to_dict()
        if include_execution:
            execution = task.executions.order_by(db.TaskExecution.start.desc()).first()
            st_task['last_execution'] = execution.to_dict() if execution else {}
        return jsonify(st_task)


default_start_date = (datetime.now() - timedelta(weeks=1)).strftime('%Y-%m-%d')

executions_parser = api.parser()
executions_parser.add_argument(
    'succeeded', type=inputs.boolean, default=True, help='Filter by success status'
)
executions_parser.add_argument(
    'produced',
    type=inputs.boolean,
    default=True,
    store_missing=False,
    help='Filter by tasks that produced entries',
)
executions_parser.add_argument(
    'start_date',
    type=inputs.datetime_from_iso8601,
    default=default_start_date,
    help='Filter by minimal start date. Example: \'2012-01-01\'. Default is 1 week ago.',
)
executions_parser.add_argument(
    'end_date',
    type=inputs.datetime_from_iso8601,
    help='Filter by maximal end date. Example: \'2012-01-01\'',
)

sort_choices = (
    'start',
    'end',
    'succeeded',
    'produced',
    'accepted',
    'rejected',
    'failed',
    'abort_reason',
)
executions_parser = api.pagination_parser(executions_parser, sort_choices=sort_choices)


@tasks_api.route('/status/<int:task_id>/executions/')
@status_api.route('/<int:task_id>/executions/')
@api.doc(parser=executions_parser, params={'task_id': 'ID of the status task'})
class TaskStatusExecutionsAPI(APIResource):
    @etag
    @api.response(200, model=task_executions)
    @api.response(NotFoundError)
    def get(self, task_id, session=None):
        """Get task executions by ID"""
        try:
            task = session.query(db.StatusTask).filter(db.StatusTask.id == task_id).one()
        except NoResultFound:
            raise NotFoundError('task status with id %d not found' % task_id)

        args = executions_parser.parse_args()

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        # Filter params
        succeeded = args.get('succeeded')
        produced = args.get('produced')
        start_date = args.get('start_date')
        end_date = args.get('end_date')

        if per_page > 100:
            per_page = 100

        start = per_page * (page - 1)
        stop = start + per_page
        descending = sort_order == 'desc'

        kwargs = {
            'start': start,
            'stop': stop,
            'task_id': task_id,
            'order_by': sort_by,
            'descending': descending,
            'succeeded': succeeded,
            'produced': produced,
            'start_date': start_date,
            'end_date': end_date,
            'session': session,
        }

        total_items = task.executions.count()

        if not total_items:
            return jsonify([])

        executions = [e.to_dict() for e in db.get_executions_by_task_id(**kwargs)]

        total_pages = int(ceil(total_items / float(per_page)))

        if page > total_pages:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(len(executions), per_page)

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Create response
        rsp = jsonify(executions)

        # Add link header to response
        rsp.headers.extend(pagination)
        return rsp
