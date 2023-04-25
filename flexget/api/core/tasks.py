import argparse
import cgi
import copy
from datetime import datetime, timedelta
from json import JSONEncoder
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any, Dict

from flask import Response, jsonify, request
from flask_restx import inputs
from sqlalchemy.orm import Session

from flexget.api import APIResource, api
from flexget.api.app import (
    APIError,
    BadRequest,
    Conflict,
    NotFoundError,
    base_message_schema,
    etag,
    success_response,
)
from flexget.config_schema import process_config
from flexget.entry import Entry
from flexget.event import event
from flexget.log import capture_logs
from flexget.options import get_parser
from flexget.task import task_phases
from flexget.terminal import capture_console
from flexget.utils import json, requests
from flexget.utils.lazy_dict import LazyLookup

# Tasks API
tasks_api = api.namespace('tasks', description='Manage Tasks')


class ObjectsContainer:
    tasks_list_object = {
        'oneOf': [
            {'type': 'array', 'items': {'$ref': '#/definitions/tasks.task'}},
            {'type': 'array', 'items': {'type': 'string'}},
        ]
    }

    task_input_object = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}, 'config': {'$ref': '/schema/plugins'}},
        'required': ['name', 'config'],
        'additionalProperties': False,
    }

    task_return_object = copy.deepcopy(task_input_object)
    task_return_object['properties']['config'] = {'type': 'object'}

    task_queue_schema = {
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer'},
                'name': {'type': 'string'},
                'current_phase': {'type': ['string', 'null']},
                'current_plugin': {'type': ['string', 'null']},
            },
        },
    }

    task_execution_results_schema = {
        'type': 'object',
        'properties': {
            'task': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'name': {'type': 'string'},
                    'stream': {
                        'type': 'array',
                        'items': {
                            'progress': {
                                'type': 'object',
                                'properties': {
                                    'status': {
                                        'type': 'string',
                                        'enum': ['pending', 'running', 'complete'],
                                    },
                                    'phase': {'type': 'string', 'enum': task_phases},
                                    'plugin': {'type': 'string'},
                                    'percent': {'type': 'float'},
                                },
                            },
                            'summary': {
                                'type': 'object',
                                'properties': {
                                    'accepted': {'type': 'integer'},
                                    'rejected': {'type': 'integer'},
                                    'failed': {'type': 'integer'},
                                    'undecided': {'type': 'integer'},
                                    'aborted': {'type': 'boolean'},
                                    'abort_reason': {'type': 'string'},
                                },
                            },
                            'entry_dump': {'type': 'array', 'items': {'type': 'object'}},
                            'log': {'type': 'string'},
                        },
                    },
                },
            }
        },
    }

    inject_input = {
        'type': 'object',
        'properties': {
            'title': {
                'type': 'string',
                'description': 'Title of the entry. If not supplied it will be attempted to retrieve it from '
                'URL headers',
            },
            'url': {'type': 'string', 'format': 'url', 'description': 'URL of the entry'},
            'force': {
                'type': 'boolean',
                'description': 'Prevent any plugins from rejecting this entry',
            },
            'accept': {
                'type': 'boolean',
                'description': 'Accept this entry immediately upon injection (disregard task filters)',
            },
            'fields': {
                'type': 'object',
                'description': 'A array of objects that can contain any other value for the entry',
            },
        },
        'required': ['url'],
    }

    task_execution_input = {
        'type': 'object',
        'properties': {
            'tasks': {
                'type': 'array',
                'items': {'type': 'string'},
                'minItems': 1,
                'uniqueItems': True,
            },
            'progress': {
                'type': 'boolean',
                'default': True,
                'description': 'Include task progress updates',
            },
            'summary': {'type': 'boolean', 'default': True, 'description': 'Include task summary'},
            'entry_dump': {
                'type': 'boolean',
                'default': True,
                'description': 'Include dump of entries including fields',
            },
            'inject': {
                'type': 'array',
                'items': inject_input,
                'description': 'A List of entry objects',
            },
            'loglevel': {
                'type': 'string',
                'description': 'Specify log level',
                'enum': ['critical', 'error', 'warning', 'info', 'verbose', 'debug', 'trace'],
            },
        },
        'required': ['tasks'],
    }

    params_return_schema = {'type': 'array', 'items': {'type': 'object'}}


tasks_list_schema = api.schema_model('tasks.list', ObjectsContainer.tasks_list_object)
task_input_schema = api.schema_model('tasks.task', ObjectsContainer.task_input_object)
task_return_schema = api.schema_model('tasks.task', ObjectsContainer.task_return_object)
task_api_queue_schema = api.schema_model('task.queue', ObjectsContainer.task_queue_schema)
task_api_execute_schema = api.schema_model(
    'task.execution', ObjectsContainer.task_execution_results_schema
)
task_execution_schema = api.schema_model(
    'task_execution_input', ObjectsContainer.task_execution_input
)
task_execution_params = api.schema_model(
    'tasks.execution_params', ObjectsContainer.params_return_schema
)

task_api_desc = (
    'Task config schema too large to display, you can view the schema using the schema API'
)

tasks_parser = api.parser()
tasks_parser.add_argument(
    'include_config', type=inputs.boolean, default=True, help='Include task config'
)


@tasks_api.route('/')
@api.doc(description=task_api_desc)
class TasksAPI(APIResource):
    @etag
    @api.response(200, model=tasks_list_schema)
    @api.doc(parser=tasks_parser)
    def get(self, session: Session = None) -> Response:
        """List all tasks"""

        active_tasks = {
            task: task_data
            for task, task_data in self.manager.user_config.get('tasks', {}).items()
            if not task.startswith('_')
        }

        args = tasks_parser.parse_args()
        if not args.get('include_config'):
            return jsonify(list(active_tasks))

        tasks = [{'name': name, 'config': config} for name, config in active_tasks.items()]
        return jsonify(tasks)

    @api.validate(task_input_schema, description='New task object')
    @api.response(201, description='Newly created task', model=task_return_schema)
    @api.response(Conflict)
    @api.response(APIError)
    def post(self, session: Session = None) -> Response:
        """Add new task"""
        data = request.json

        task_name = data['name']

        if task_name in self.manager.user_config.get('tasks', {}):
            raise Conflict('task already exists')

        if 'tasks' not in self.manager.user_config:
            self.manager.user_config['tasks'] = {}
        if 'tasks' not in self.manager.config:
            self.manager.config['tasks'] = {}

        task_schema_processed = copy.deepcopy(data)
        errors = process_config(
            task_schema_processed, schema=task_input_schema.__schema__, set_defaults=True
        )

        if errors:
            raise APIError('problem loading config, raise a BUG as this should not happen!')

        self.manager.user_config['tasks'][task_name] = data['config']
        self.manager.config['tasks'][task_name] = task_schema_processed['config']

        self.manager.save_config()
        self.manager.config_changed()
        rsp = jsonify({'name': task_name, 'config': self.manager.user_config['tasks'][task_name]})
        rsp.status_code = 201
        return rsp


@tasks_api.route('/<task>/')
@api.doc(params={'task': 'task name'}, description=task_api_desc)
@api.response(APIError, description='unable to read config')
class TaskAPI(APIResource):
    @etag
    @api.response(200, model=task_return_schema)
    @api.response(NotFoundError, description='task not found')
    def get(self, task, session: Session = None) -> Response:
        """Get task config"""
        if task not in self.manager.user_config.get('tasks', {}):
            raise NotFoundError(f'task `{task}` not found')

        return jsonify({'name': task, 'config': self.manager.user_config['tasks'][task]})

    @api.validate(task_input_schema)
    @api.response(200, model=task_return_schema)
    @api.response(NotFoundError)
    @api.response(BadRequest)
    def put(self, task, session: Session = None) -> Response:
        """Update tasks config"""
        data = request.json

        new_task_name = data['name']

        if task not in self.manager.user_config.get('tasks', {}):
            raise NotFoundError(f'task `{task}` not found')

        if 'tasks' not in self.manager.user_config:
            self.manager.user_config['tasks'] = {}
        if 'tasks' not in self.manager.config:
            self.manager.config['tasks'] = {}

        if task != new_task_name:
            # Rename task
            if new_task_name in self.manager.user_config['tasks']:
                raise BadRequest('cannot rename task as it already exist')

            del self.manager.user_config['tasks'][task]
            del self.manager.config['tasks'][task]

        # Process the task config
        task_schema_processed = copy.deepcopy(data)
        errors = process_config(
            task_schema_processed, schema=task_return_schema.__schema__, set_defaults=True
        )

        if errors:
            raise APIError('problem loading config, raise a BUG as this should not happen!')

        self.manager.user_config['tasks'][new_task_name] = data['config']
        self.manager.config['tasks'][new_task_name] = task_schema_processed['config']

        self.manager.save_config()
        self.manager.config_changed()

        rsp = jsonify(
            {'name': new_task_name, 'config': self.manager.user_config['tasks'][new_task_name]}
        )
        rsp.status_code = 200
        return rsp

    @api.response(200, model=base_message_schema, description='deleted task')
    @api.response(NotFoundError)
    def delete(self, task, session: Session = None) -> Response:
        """Delete a task"""
        try:
            self.manager.config['tasks'].pop(task)
            self.manager.user_config['tasks'].pop(task)
        except KeyError:
            raise NotFoundError('task does not exist')

        self.manager.save_config()
        self.manager.config_changed()
        return success_response('successfully deleted task')


default_start_date = (datetime.now() - timedelta(weeks=1)).strftime('%Y-%m-%d')

status_parser = api.parser()
status_parser.add_argument(
    'succeeded', type=inputs.boolean, default=True, help='Filter by success status'
)
status_parser.add_argument(
    'produced',
    type=inputs.boolean,
    default=True,
    store_missing=False,
    help='Filter by tasks that produced entries',
)
status_parser.add_argument(
    'start_date',
    type=inputs.datetime_from_iso8601,
    default=default_start_date,
    help='Filter by minimal start date. Example: \'2012-01-01\'',
)
status_parser.add_argument(
    'end_date',
    type=inputs.datetime_from_iso8601,
    help='Filter by maximal end date. Example: \'2012-01-01\'',
)
status_parser.add_argument(
    'limit',
    default=100,
    type=int,
    help='Limit return of executions per task, as that number can be huge',
)


def _task_info_dict(task):
    return {
        'id': int(task.id),
        'name': task.name,
        'current_phase': task.current_phase,
        'current_plugin': task.current_plugin,
    }


@tasks_api.route('/queue/')
class TaskQueueAPI(APIResource):
    @api.response(200, model=task_api_queue_schema)
    def get(self, session: Session = None) -> Response:
        """List task(s) in queue for execution"""
        tasks = [_task_info_dict(task) for task in self.manager.task_queue.run_queue.queue]

        if self.manager.task_queue.current_task:
            tasks.insert(0, _task_info_dict(self.manager.task_queue.current_task))

        return jsonify(tasks)


class ExecuteLog(Queue):
    """Supports task log streaming by acting like a file object"""

    def write(self, s):
        self.put(json.dumps({'log': s}))


if TYPE_CHECKING:
    from typing import TypedDict

    class StreamTaskDict(TypedDict):
        queue: ExecuteLog
        last_update: datetime
        args: Dict[str, Any]

    _streams: Dict[str, StreamTaskDict]
_streams = {}

# Another namespace for the same endpoint
inject_api = api.namespace('inject', description='Entry injection API')


@inject_api.route('/params/')
@tasks_api.route('/execute/params/')
@api.doc(description='Available payload parameters for task execute')
class TaskExecutionParams(APIResource):
    @etag(cache_age=3600)
    @api.response(200, model=task_execution_params)
    def get(self, session: Session = None) -> Response:
        """Execute payload parameters"""
        return jsonify(ObjectsContainer.task_execution_input)


@inject_api.route('/')
@tasks_api.route('/execute/')
@api.doc(description='For details on available parameters query /params/ endpoint')
class TaskExecutionAPI(APIResource):
    @api.response(NotFoundError)
    @api.response(BadRequest)
    @api.response(200, model=task_api_execute_schema)
    @api.validate(task_execution_schema)
    def post(self, session: Session = None) -> Response:
        """Execute task and stream results"""
        data = request.json
        for task in data.get('tasks'):
            if task.lower() not in [
                t.lower() for t in self.manager.user_config.get('tasks', {}).keys()
            ]:
                raise NotFoundError(f'task {task} does not exist')

        queue = ExecuteLog()
        output = queue if data.get('loglevel') else None
        stream = (
            True
            if any(
                arg[0] in ['progress', 'summary', 'loglevel', 'entry_dump']
                for arg in data.items()
                if arg[1]
            )
            else False
        )
        loglevel = data.pop('loglevel', None)

        if loglevel:
            loglevel = loglevel.upper()

        # This emulates the CLI command of using `--now` and `no-cache`
        options = {
            'interval_ignore': data.pop('now', None),
            'nocache': data.pop('no_cache', None),
            'allow_manual': True,
        }

        for option, value in data.items():
            options[option] = value

        if data.get('inject'):
            entries = []
            for item in data.get('inject'):
                entry = Entry()
                entry['url'] = item['url']
                if not item.get('title'):
                    try:
                        value, params = cgi.parse_header(
                            requests.head(item['url']).headers['Content-Disposition']
                        )
                        entry['title'] = params['filename']
                    except KeyError:
                        raise BadRequest(
                            'No title given, and couldn\'t get one from the URL\'s HTTP response'
                        )

                else:
                    entry['title'] = item.get('title')
                if item.get('force'):
                    entry['immortal'] = True
                if item.get('accept'):
                    entry.accept(reason='accepted by API inject')
                if item.get('fields'):
                    for key, value in item.get('fields').items():
                        entry[key] = value
                entries.append(entry)
            options['inject'] = entries

        if output:
            with capture_console(output), capture_logs(output, level=loglevel):
                executed_tasks = self.manager.execute(options=options)
        else:
            executed_tasks = self.manager.execute(options=options)

        tasks_queued = []

        for task_id, task_name, task_event in executed_tasks:
            tasks_queued.append({'id': task_id, 'name': task_name, 'event': task_event})
            _streams[task_id] = {'queue': queue, 'last_update': datetime.now(), 'args': data}

        if not stream:
            return jsonify(
                {'tasks': [{'id': task['id'], 'name': task['name']} for task in tasks_queued]}
            )

        def stream_response():
            # First return the tasks to execute
            yield '{"stream": ['
            yield json.dumps(
                {'tasks': [{'id': task['id'], 'name': task['name']} for task in tasks_queued]}
            ) + ',\n'

            while True:
                try:
                    yield queue.get(timeout=1) + ',\n'
                    continue
                except Empty:
                    pass

                if queue.empty() and all(task['event'].is_set() for task in tasks_queued):
                    for task in tasks_queued:
                        del _streams[task['id']]
                    break
            yield '{}]}'

        return Response(stream_response(), mimetype='text/event-stream')


@event('manager.daemon.started')
def setup_params(mgr):
    parser = get_parser('execute')

    for action in parser._optionals._actions:
        # Ignore list for irrelevant actions
        ignore = ['help', 'verbose', 'silent', 'try-regexp', 'dump-config', 'dump']

        name = action.option_strings[-1].strip('--')
        if name in ignore or action.help == '==SUPPRESS==':
            continue

        name = name.replace('-', '_')
        property_data = {'description': action.help.capitalize()}
        if isinstance(action, argparse._StoreConstAction):
            property_data['type'] = 'boolean'
        elif isinstance(action, argparse._StoreAction):
            if action.nargs in ['+', '*']:
                property_data['type'] = 'array'
                property_data['items'] = {'type': 'string'}
                property_data['minItems'] = 1
            else:
                property_data['type'] = 'string'
        else:
            # Unknown actions should not be added to schema
            property_data = None

        # Some options maybe pre-added to schema with additional options, don't override them
        if property_data and name not in ObjectsContainer.task_execution_input['properties']:
            ObjectsContainer.task_execution_input['properties'][name] = property_data

    ObjectsContainer.task_execution_input['additionalProperties'] = False


class EntryDecoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, LazyLookup):
            return '<LazyField>'

        try:
            return JSONEncoder.default(self, o)
        except TypeError:
            return str(o)


_phase_percents = {
    'input': 5,
    'metainfo': 10,
    'filter': 30,
    'download': 40,
    'modify': 65,
    'output': 75,
    'exit': 100,
}


def update_stream(task, status: str = 'pending') -> None:
    if task.current_phase in _phase_percents:
        task.stream['percent'] = _phase_percents[task.current_phase]

    progress = {
        'status': status,
        'phase': task.current_phase,
        'plugin': task.current_plugin,
        'percent': task.stream.get('percent', 0),
    }

    task.stream['queue'].put(json.dumps({'progress': progress, 'task_id': task.id}))


@event('task.execute.started')
def start_task(task):
    task.stream = _streams.get(task.id)

    if task.stream and task.stream['args'].get('progress'):
        update_stream(task, status='running')


@event('task.execute.completed')
def finish_task(task):
    if task.stream:
        if task.stream['args'].get('progress'):
            update_stream(task, status='complete')

        if task.stream['args'].get('entry_dump'):
            entries = [entry.store for entry in task.entries]
            task.stream['queue'].put(
                EntryDecoder().encode({'entry_dump': entries, 'task_id': task.id})
            )

        if task.stream['args'].get('summary'):
            task.stream['queue'].put(
                json.dumps(
                    {
                        'summary': {
                            'accepted': len(task.accepted),
                            'rejected': len(task.rejected),
                            'failed': len(task.failed),
                            'undecided': len(task.undecided),
                            'aborted': task.aborted,
                            'abort_reason': task.abort_reason,
                        },
                        'task_id': task.id,
                    }
                )
            )


@event('task.execute.before_plugin')
def track_progress(task, plugin_name: str):
    if task.stream and task.stream['args'].get('progress'):
        update_stream(task, status='running')
