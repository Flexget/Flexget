import copy
from flask import request
from flexget.config_schema import process_config
from flexget.api import api, APIResource, ApiError, NotFoundError
from datetime import datetime
from Queue import Queue, Empty
import cherrypy
from flask import jsonify, Response
from flexget.task import task_phases
from flexget.utils import json
from json import JSONEncoder
from flexget.event import event
from flexget.utils.lazy_dict import LazyLookup
import flask_restplus

# Tasks API
tasks_api = api.namespace('tasks', description='Manage Tasks')

tasks_list_api_schema = api.schema('tasks.list', {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {'$ref': '#/definitions/tasks.task'}
        }
    },
    'additionalProperties': False
})


task_schema_validate = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'config': {'$ref': '/schema/plugins'}
    },
    'additionalProperties': False
}


task_schema = copy.deepcopy(task_schema_validate)
task_schema['properties']['config'] = {'type': 'object'}

task_api_schema = api.schema('tasks.task', task_schema)

task_api_desc = 'Task config schema too large to display, you can view the schema using the schema API'


@tasks_api.route('/')
@api.doc(description=task_api_desc)
class TasksAPI(APIResource):
    @api.response(200, model=tasks_list_api_schema)
    def get(self, session=None):
        """ List all tasks """
        tasks = []
        for name, config in self.manager.user_config.get('tasks', {}).iteritems():
            tasks.append({'name': name, 'config': config})
        return {'tasks': tasks}

    @api.validate(task_api_schema, schema_override=task_schema_validate, description='New task object')
    @api.response(201, description='Newly created task', model=task_api_schema)
    @api.response(409, description='Task already exists')
    def post(self, session=None):
        """ Add new task """
        data = request.json

        task_name = data['name']

        if task_name in self.manager.user_config.get('tasks', {}):
            return {'error': 'task already exists'}, 409

        if 'tasks' not in self.manager.user_config:
            self.manager.user_config['tasks'] = {}
        if 'tasks' not in self.manager.config:
            self.manager.config['tasks'] = {}

        task_schema_processed = copy.deepcopy(data)
        errors = process_config(task_schema_processed, schema=task_api_schema.__schema__, set_defaults=True)

        if errors:
            return {'error': 'problem loading config, raise a BUG as this should not happen!'}, 500

        self.manager.user_config['tasks'][task_name] = data['config']
        self.manager.config['tasks'][task_name] = task_schema_processed['config']

        self.manager.save_config()
        self.manager.config_changed()
        return {'name': task_name, 'config': self.manager.user_config['tasks'][task_name]}, 201


@tasks_api.route('/<task>/')
@api.doc(params={'task': 'task name'}, description=task_api_desc)
class TaskAPI(APIResource):
    @api.response(200, model=task_api_schema)
    @api.response(NotFoundError, description='task not found')
    @api.response(ApiError, description='unable to read config')
    def get(self, task, session=None):
        """ Get task config """
        if task not in self.manager.user_config.get('tasks', {}):
            raise NotFoundError('task `%s` not found' % task)

        return {'name': task, 'config': self.manager.user_config['tasks'][task]}

    @api.validate(task_api_schema, schema_override=task_schema_validate)
    @api.response(200, model=task_api_schema)
    @api.response(201, description='renamed task', model=task_api_schema)
    @api.response(404, description='task does not exist', model=task_api_schema)
    @api.response(400, description='cannot rename task as it already exist', model=task_api_schema)
    def put(self, task, session=None):
        """ Update tasks config """
        data = request.json

        new_task_name = data['name']

        if task not in self.manager.user_config.get('tasks', {}):
            return {'error': 'task does not exist'}, 404

        if 'tasks' not in self.manager.user_config:
            self.manager.user_config['tasks'] = {}
        if 'tasks' not in self.manager.config:
            self.manager.config['tasks'] = {}

        code = 200
        if task != new_task_name:
            # Rename task
            if new_task_name in self.manager.user_config['tasks']:
                return {'error': 'cannot rename task as it already exist'}, 400

            del self.manager.user_config['tasks'][task]
            del self.manager.config['tasks'][task]
            code = 201

        # Process the task config
        task_schema_processed = copy.deepcopy(data)
        errors = process_config(task_schema_processed, schema=task_api_schema.__schema__, set_defaults=True)

        if errors:
            return {'error': 'problem loading config, raise a BUG as this should not happen!'}, 500

        self.manager.user_config['tasks'][new_task_name] = data['config']
        self.manager.config['tasks'][new_task_name] = task_schema_processed['config']

        self.manager.save_config()
        self.manager.config_changed()

        return {'name': new_task_name, 'config': self.manager.user_config['tasks'][new_task_name]}, code

    @api.response(200, description='deleted task')
    @api.response(404, description='task not found')
    def delete(self, task, session=None):
        """ Delete a task """
        try:
            self.manager.config['tasks'].pop(task)
            self.manager.user_config['tasks'].pop(task)
        except KeyError:
            return {'error': 'invalid task'}, 404

        self.manager.save_config()
        self.manager.config_changed()
        return {}


def _task_info_dict(task):
    return {
        'id': int(task.id),
        'name': task.name,
        'current_phase': task.current_phase,
        'current_plugin': task.current_plugin,
    }


task_queue_schema = {
    'type': 'object',
    'properties': {
        'tasks': {
            'type': 'array',
            'items': {
                'id': {'type': 'integer'},
                'name': {'type': 'string'},
                'current_phase': {'type': 'string'},
                'current_plugin': {'type': 'string'},
            }
        }
    }
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
                                'status': {'type': 'string', 'enum': ['pending', 'running', 'complete']},
                                'phase': {'type': 'string', 'enum': task_phases},
                                'plugin': {'type': 'string'},
                                'percent': {'type': 'float'}
                            }
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
                            }
                        },
                        'entry_dump': {'type': 'array', 'items': {'type': 'object'}},
                        'log': {'type': 'string'}
                    }
                }
            }
        }
    }
}

task_api_queue_schema = api.schema('task.queue', task_queue_schema)
task_api_execute_schema = api.schema('task.execution', task_execution_results_schema)


@tasks_api.route('/queue/')
class TaskQueueAPI(APIResource):
    @api.response(200, model=task_api_queue_schema)
    def get(self, session=None):
        """ List task(s) in queue for execution """
        tasks = [_task_info_dict(task) for task in self.manager.task_queue.run_queue.queue]

        if self.manager.task_queue.current_task:
            tasks.insert(0, _task_info_dict(self.manager.task_queue.current_task))

        return jsonify({'tasks': tasks})


class ExecuteLog(Queue):
    """ Supports task log streaming by acting like a file object """

    def write(self, s):
        self.put(json.dumps({'log': s}))


stream_parser = api.parser()

stream_parser.add_argument('progress', type=flask_restplus.inputs.boolean, required=False, default=True,
                           help='Include task progress updates')
stream_parser.add_argument('summary', type=flask_restplus.inputs.boolean, required=False, default=True,
                           help='Include task summary')
stream_parser.add_argument('log', type=flask_restplus.inputs.boolean, required=False, default=False,
                           help='Include execution log')
stream_parser.add_argument('entry_dump', type=flask_restplus.inputs.boolean, required=False, default=False,
                           help='Include dump of entries including fields')

_streams = {}


@tasks_api.route('/<task>/execute/')
@api.doc(params={'task': 'task name'})
class TaskExecutionAPI(APIResource):
    @api.response(404, description='task not found')
    @api.response(200, model=task_api_execute_schema)
    @api.doc(parser=stream_parser)
    def get(self, task, session=None):
        """ Execute task and stream results """
        args = stream_parser.parse_args()

        if task.lower() not in [t.lower() for t in self.manager.user_config.get('tasks', {}).iterkeys()]:
            return {'error': 'task does not exist'}, 404

        queue = ExecuteLog()
        output = queue if args['log'] else None
        stream = True if any(
            arg[0] in ['progress', 'summary', 'log', 'entry_dump'] for arg in args.iteritems() if arg[1]) else False

        task_id, __, task_event = self.manager.execute(options={'tasks': [task]}, output=output)[0]

        if not stream:
            return {'task': {'id': task_id, 'name': task}}

        _streams[task_id] = {
            'queue': queue,
            'last_update': datetime.now(),
            'args': args
        }

        def stream_response():
            yield '{"task": {"id": "%s", "name": "%s", "stream": [' % (task_id, task)

            while True:
                # If the server is shutting down then end the stream nicely
                if cherrypy.engine.state != cherrypy.engine.states.STARTED:
                    break

                try:
                    yield queue.get(timeout=1) + ',\n'
                    continue
                except Empty:
                    pass

                if queue.empty() and task_event.is_set():
                    del _streams[task_id]
                    break
            yield '{}]}}'

        return Response(stream_response(), mimetype='text/event-stream')


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


def update_stream(task, status='pending'):
    if task.current_phase in _phase_percents:
        task.stream['percent'] = _phase_percents[task.current_phase]

    progress = {
        'status': status,
        'phase': task.current_phase,
        'plugin': task.current_plugin,
        'percent': task.stream.get('percent', 0)
    }

    task.stream['queue'].put(json.dumps({'progress': progress}))


@event('task.execute.started')
def start_task(task):
    task.stream = _streams.get(task.id)

    if task.stream and task.stream['args']['progress']:
        update_stream(task, status='running')


@event('task.execute.completed')
def finish_task(task):
    if task.stream:
        if task.stream['args']['progress']:
            update_stream(task, status='complete')

        if task.stream['args']['entry_dump']:
            entries = [entry.store for entry in task.entries]
            task.stream['queue'].put(EntryDecoder().encode({'entry_dump': entries}))

        if task.stream['args']['summary']:
            task.stream['queue'].put(json.dumps({
                'summary': {
                    'accepted': len(task.accepted),
                    'rejected': len(task.rejected),
                    'failed': len(task.failed),
                    'undecided': len(task.undecided),
                    'aborted': task.aborted,
                    'abort_reason': task.abort_reason,
                }
            }))


@event('task.execute.before_plugin')
def track_progress(task, plugin_name):
    if task.stream and task.stream['args']['progress']:
        update_stream(task, status='running')
