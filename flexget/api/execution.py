from Queue import Queue
from Queue import Empty

from flask import request, jsonify, Response

from flexget.options import get_parser
from flexget.api import api, APIResource
from flexget.utils import json
from flexget import plugin
from flexget.event import event

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
@api.doc(description='Execution ID\'s are only valid for the life of the task')
class ExecutionAPI(APIResource):
    @api.validate(execute_api_task_schema)
    @api.response(400, 'invalid options specified')
    @api.response(200, 'List of tasks queued for execution')
    def post(self, session=None):
        """ Execute task(s) """
        options = request.json or {}
        args = stream_parser.parse_args()

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


class LogStream(Queue):
    def write(self, s):
        self.put(json.dumps({'log': s}))


stream_parser = api.parser()
stream_parser.add_argument('progress', type=bool, required=False, default=True, help='Stream log data')
stream_parser.add_argument('log', type=bool, required=False, default=True, help='Stream task log')

_streams = {}


@execution_api.route('/stream/')
@api.doc(description='Execution ID\'s are only valid for the life of the task')
class ExecutionAPIStream(APIResource):
    @api.validate(execute_api_task_schema)
    @api.response(400, 'invalid options specified')
    @api.response(200, 'Execution stream with task progress and/or log')
    @api.doc(parser=stream_parser)
    def post(self, session=None):
        """ Execute task(s) """
        options = request.json or {}
        args = stream_parser.parse_args()

        options_string = options.pop('options_string', '')
        if options_string:
            try:
                options['options'] = get_parser('execute').parse_args(options_string, raise_errors=True)
            except ValueError as e:
                return {'error': 'invalid options_string specified: %s' % e.message}, 400

        if args['progress'] or args['log']:
            stream = LogStream()

        output = stream if args['log'] else None

        tasks_queued = []

        for task_id, task_name, task_event in self.manager.execute(options=options, output=output):
            tasks_queued.append({'id': task_id, 'name': task_name, 'event': task_event})
            _streams[task_id] = stream

        def stream_response():
            # First return the tasks to execute
            yield '{"stream": ['
            yield json.dumps({'tasks': [{'id': task['id'], 'name': task['name']} for task in tasks_queued]}) + ','

            while True:
                try:
                    yield stream.get(timeout=1) + ','
                    continue
                except Empty:
                    pass

                if stream.empty() and all([task['event'].is_set() for task in tasks_queued]):
                    for task in tasks_queued:
                        del _streams[task['id']]
                    break
            yield '{}]}'
        return Response(stream_response(), mimetype='text/event-stream')


def update_stream(task, status='pending'):
    stream = _streams[task.id]

    progress = {
        'status': status,
        'phase': task.current_phase,
        'plugin': task.current_plugin,
    }

    stream.put(json.dumps({'progress': {task.id: progress}}))


@event('task.execute.started')
def start_progress(task):
    task.stream = _streams.get(task.id)

    if task.stream:
        update_stream(task, status='running')


@event('task.execute.completed')
def finish_progress(task):
    if task.stream:
        update_stream(task, status='complete')


@event('task.execute.before_plugin')
def track_progress(task, plugin_name):
    if task.stream:
        update_stream(task, status='running')


def on_entry_action(entry, act=None, reason=None, **kwargs):
    if not reason and entry.get('%s_by' % act):
        reason = '%s by %s' % (act, entry['%s_by' % act])

    entry.task.stream.put(json.dumps({
        'entry': {
            entry.task.id: {
                'title': entry['title'],
                'url': entry['url'],
                'state': act,
                'reason': reason,
            }
        }
    }))


class EntryTracker(object):

    @plugin.priority(-255)
    def on_task_abort(self, task, config):
        if not task.stream:
            return

        update_stream(task, status='aborted')

    @plugin.priority(-255)
    def on_task_input(self, task, config):
        if not task.stream:
            return

        # TODO: Cleanup old streams

        # Register callbacks to update the status of an entry and send initial entry list
        for entry in task.all_entries:
            entry.on_accept(on_entry_action, act='accepted')
            entry.on_reject(on_entry_action, act='rejected')
            entry.on_fail(on_entry_action, act='failed')

            on_entry_action(entry, act='undecided')


@event('plugin.register')
def register_plugin():
    plugin.register(EntryTracker, 'entry_tracker', builtin=True, api_ver=2)
