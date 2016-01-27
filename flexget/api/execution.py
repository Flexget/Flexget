from datetime import datetime
from Queue import Queue, Empty
import cherrypy
from flask import jsonify, Response
from flexget.task import task_phases
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

execution_results_schema = {
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

execution_api_queue_schema = api.schema('execution_queue', task_queue_schema)
execution_api_result_schema = api.schema('execution_result', execution_results_schema)


@execution_api.route('/')
class ExecutionQueueAPI(APIResource):
    @api.response(200, 'Show tasks in queue for execution', execution_api_queue_schema)
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

stream_parser.add_argument('progress', type=bool, required=False, default=True, help='Include task progress updates')
stream_parser.add_argument('summary', type=bool, required=False, default=True, help='Include task summary')
stream_parser.add_argument('log', type=bool, required=False, default=False, help='Include execution log')
stream_parser.add_argument('entry_dump', type=bool, required=False, default=False,
                           help='Include dump of entries including fields')

_streams = {}


@execution_api.route('/execute/<task_name>/')
@api.doc(description='Wildcards supported ie: TV* will execute all tasks with TV in the name')
class ExecutionAPI(APIResource):
    @api.response(404, 'task not found')
    @api.response(200, 'Execution task with optional progress and/or log stream', execution_api_result_schema)
    @api.doc(parser=stream_parser)
    def get(self, task_name, session=None):
        """ Execute task and stream results """
        args = stream_parser.parse_args()

        if task_name.lower() not in [task.lower() for task in self.manager.user_config.get('tasks', {}).iterkeys()]:
            return {'error': 'task does not exist'}, 404

        queue = ExecuteLog()
        output = queue if args['log'] else None
        stream = True if any(
            arg[0] in ['progress', 'summary', 'log', 'entry_dump'] for arg in args.iteritems() if arg[1]) else False

        task_id, __, task_event = self.manager.execute(options={'tasks': [task_name]}, output=output)[0]

        if not stream:
            return {'task': {'id': task_id, 'name': task_name}}

        _streams[task_id] = {
            'queue': queue,
            'last_update': datetime.now(),
            'args': args
        }

        def stream_response():
            yield '{"task": {"id": "%s", "name": "%s", "stream": [' % (task_id, task_name)

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
