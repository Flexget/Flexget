from datetime import datetime
from Queue import Queue, Empty

from flask import request, jsonify, Response

from flexget.options import get_parser
from flexget.api import api, APIResource
from flexget.utils import json
from json import JSONEncoder
from flexget.event import event
from flexget.utils.lazy_dict import LazyLookup

execution_api = api.namespace('execution', description='Execute tasks')


def _task_info_dict(task):
    return {
        'id': int(task.id),
        'name': task.name,
        'current_phase': task.current_phase,
        'current_plugin': task.current_plugin,
    }


task_info_schema = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer'},
        'name': {'type': 'string'},
        'current_phase': {'type': 'string'},
        'current_plugin': {'type': 'string'},
    }
}

execution_results_schema = {
    'type': 'object',
    'properties': {
        'tasks': {
            'type': 'array',
            'items': task_info_schema,
        }
    }
}


execute_task_schema = {
    'type': 'object',
    'properties': {
        'tasks': {
            'type': 'array',
            'items': {'type': 'string'}
        },
        'opt': {'type': 'string'},
    }
}


execution_api_result_schema = api.schema('execution_result', execution_results_schema)
execute_api_task_schema = api.schema('execute_task', execute_task_schema)


@execution_api.route('/queue/')
class ExecutionQueueAPI(APIResource):

    @api.response(200, 'Show tasks in queue for execution', execution_api_result_schema)
    def get(self, session=None):
        """ List task executions """
        tasks = [_task_info_dict(task) for task in self.manager.task_queue.run_queue.queue]

        if self.manager.task_queue.current_task:
            tasks.insert(0, _task_info_dict(self.manager.task_queue.current_task))

        return jsonify({'tasks': tasks})


@execution_api.route('/execute/')
@api.doc(description='Wildcards supported ie: TV* will execute all tasks with TV in the name')
class ExecutionAPI(APIResource):
    @api.validate(execute_api_task_schema)
    @api.response(400, 'invalid options specified')
    @api.response(200, 'List of tasks queued for execution')
    def post(self, session=None):
        """ Execute task(s) """
        options = request.json or {}

        options_string = options.pop('options_string', '')
        if options_string:
            try:
                options['options'] = get_parser('execute').parse_args(options_string, raise_errors=True)
            except ValueError as e:
                return {'error': 'invalid options_string specified: %s' % e.message}, 400

        tasks = [{'id': task_id, 'name': task_name}
                 for task_id, task_name, task_event
                 in self.manager.execute(options=options)]

        return {'tasks': tasks}


class ExecuteQueue(Queue):
    """ Supports task log streaming by acting like a file object """
    def write(self, s):
        self.put(json.dumps({'log': s}))


stream_parser = api.parser()

stream_parser.add_argument('progress', type=bool, required=False, default=True, help='Include task progress updates')
stream_parser.add_argument('summary', type=bool, required=False, default=True, help='Include task summary')
stream_parser.add_argument('log', type=bool, required=False, default=False, help='Include execution log')
stream_parser.add_argument('entry_dump', type=bool, required=False, default=False, help='Include dump of entries including fields')

_streams = {}


@execution_api.route('/execute/stream/')
@api.doc(description='Wildcards supported ie: TV* will execute all tasks with TV in the name')
class ExecutionAPIStream(APIResource):
    @api.validate(execute_api_task_schema)
    @api.response(400, 'invalid options specified')
    @api.response(200, 'Execution stream with task progress and/or log')
    @api.doc(parser=stream_parser)
    def post(self, session=None):
        """ Execute task(s) and stream results """
        options = request.json or {}
        args = stream_parser.parse_args()

        options_string = options.pop('options_string', '')
        if options_string:
            try:
                options['options'] = get_parser('execute').parse_args(options_string, raise_errors=True)
            except ValueError as e:
                return {'error': 'invalid options_string specified: %s' % e.message}, 400

        queue = ExecuteQueue()
        output = queue if args['log'] else None

        tasks_queued = []

        for task_id, task_name, task_event in self.manager.execute(options=options, output=output):
            tasks_queued.append({'id': task_id, 'name': task_name, 'event': task_event})
            _streams[task_id] = {
                'queue': queue,
                'last_update': datetime.now(),
                'args': args
            }

        def stream_response():
            # First return the tasks to execute
            yield '{"stream": ['
            yield json.dumps({'tasks': [{'id': task['id'], 'name': task['name']} for task in tasks_queued]}) + ',\n'

            while True:
                try:
                    yield queue.get(timeout=1) + ',\n'
                    continue
                except Empty:
                    pass

                if queue.empty() and all([task['event'].is_set() for task in tasks_queued]):
                    for task in tasks_queued:
                        del _streams[task['id']]
                    break
            yield '{}]}'
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

    task.stream['queue'].put(json.dumps({'progress': {task.id: progress}}))


@event('task.execute.started')
def start_task(task):
    task.stream = _streams.get(task.id)

    if task.stream:
        update_stream(task, status='running')


@event('task.execute.completed')
def finish_task(task):
    if task.stream:
        update_stream(task, status='complete')

        if task.stream['args']['entry_dump']:
            entries = [entry.store for entry in task.entries]
            task.stream['queue'].put(EntryDecoder().encode({'entry_dump': {task.id: entries}}))

        if task.stream['args']['summary']:
            task.stream['queue'].put(json.dumps({
                'summary': {
                    task.id: {
                        'accepted': len(task.accepted),
                        'rejected': len(task.rejected),
                        'failed': len(task.failed),
                        'undecided': len(task.undecided),
                        'aborted': task.aborted,
                        'abort_reason': task.abort_reason,
                    }
                }
            }))


@event('task.execute.before_plugin')
def track_progress(task, plugin_name):
    if task.stream:
        update_stream(task, status='running')
