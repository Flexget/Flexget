import logging
import os
from Queue import Queue
from Queue import Empty
from time import sleep

from flask import request, jsonify, Response

from flexget.options import get_parser
from flexget.api import api, APIResource
from flexget.utils import json
from flexget import plugin
from flexget.event import event

execution_api = api.namespace('execution', description='Execute tasks')


log = logging.getLogger('execute_api')

def _task_info_dict(task):
    return {
        'id': int(task.id),
        'name': task.name,
        'current_phase': task.current_phase,
        'current_plugin': task.current_plugin,
    }


task_info_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
        "current_phase": {"type": "string"},
        "current_plugin": {"type": "string"},
    }
}

execution_results_schema = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": task_info_schema,
        }
    }
}


execute_task_schema = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {"type": "string"}
        },
        "opt": {"type": "string"},
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

        return jsonify({"tasks": tasks})


stream_parser = api.parser()
stream_parser.add_argument('progress', type=bool, required=False, default=False, help='Stream log data')
stream_parser.add_argument('log', type=bool, required=False, default=False, help='Stream task log')

_streams = {}


@execution_api.route('/execute/')
@api.doc(description='Execution ID\'s are only valid for the life of the task')
class ExecutionAPI(APIResource):
    @api.validate(execute_api_task_schema)
    @api.response(400, 'invalid options specified')
    @api.response(200, 'List of tasks queued for execution')
    @api.response(200, 'Execution stream with task progress and/or log')
    @api.doc(parser=stream_parser)
    def post(self, session=None):
        """ Execute task(s) """
        kwargs = request.json or {}
        args = stream_parser.parse_args()

        options_string = kwargs.pop('options_string', '')
        if options_string:
            try:
                kwargs['options'] = get_parser('execute').parse_args(options_string, raise_errors=True)
            except ValueError as e:
                return {'error': 'invalid options_string specified: %s' % e.message}, 400

        tasks_queued = {'tasks': []}
        tasks = {}
        for task_id, task_event in self.manager.execute(options=kwargs):
            tasks[task_id] = task_event

        for queued_task in self.manager.task_queue.run_queue.queue:
            if queued_task.id in tasks.keys():
                tasks_queued['tasks'].append({'id': queued_task.id, 'name': queued_task.name})

        if not args['progress'] and not args['log']:
            return tasks_queued

        # Insert streams for each task
        for task_id in tasks.keys():
            _streams[task_id] = Queue()

        def execute_stream():

            # First return the tasks to execute
            yield json.dumps(tasks_queued) + '\n'

            for task_id, task_event in tasks.iteritems():
                stream = _streams[task_id]

                while True:
                    try:
                        update = stream.get(timeout=1)
                        yield json.dumps({'progress': {task_id: update}}) + '\n'
                    except Empty:
                        pass

                    if task_event.is_set() and stream.empty():
                        break

            """
            f = open(os.path.join(self.manager.config_base, 'log-%s.json' % self.manager.config_name), 'r')
            while True:
                if not task_info.started:
                    continue

                # First check if it has finished, if there is no new lines then we can return
                finished = task_info.finished is not None
                line = f.readline()
                if not line:
                    if finished:
                        return
                    sleep(0.5)
                    line = '{}'
                    yield line

                record = json.loads(line)
                if record.get('task_id') != exec_id:
                    continue
                yield line
            """

        return Response(execute_stream(), mimetype='text/event-stream')


def queue_update(task):
    stream = _streams[task.id]

    progress = {
        'entries': {
            'accepted': [entry['title'] for entry in task.accepted],
            'rejected': [entry['title'] for entry in task.rejected],
            'failed': [entry['title'] for entry in task.failed],
        },
        'phase': task.current_phase,
        'plugin': task.current_plugin,
    }

    stream.put({'progress': progress})


@event('task.execute.completed')
def finish_progress(task):
    if task.id not in _streams:
        return
    queue_update(task)


@event('task.execute.before_plugin')
def track_progress(task, plugin_name):
    if task.id not in _streams:
        return
    queue_update(task)
