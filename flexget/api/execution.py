import os
from time import sleep

from flask import request, jsonify, Response

from flexget.options import get_parser
from flexget.api import api, APIResource, NotFoundError
from flexget.utils import json

execution_api = api.namespace('execution', description='Execute tasks')


def _task_info_dict(task_info):
    return {
        'id': int(task_info.id),
        'name': task_info.name,
        'status': task_info.status,
        'created': task_info.created,
        'started': task_info.started,
        'finished': task_info.finished,
        'message': task_info.message,
        'log': {'href': '/execution/%s/log/' % task_info.id},
    }


task_execution_api_schema = {
    "type": "object",
    "properties": {
        "created": {"type": "string"},
        "finished": {"type": "string"},
        "id": {"type": "integer"},
        "log": {
            "type": "object",
            "properties": {
                "href": {
                    "type": "string"
                }
            }
        },
        "message": {"type": "string"},
        "name": {"type": "string"},
        "started": {"type": "string"},
        "status": {"type": "string"}
    }
}

tasks_execution_api_schema = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": task_execution_api_schema
        }
    }
}


task_execution_api_schema = api.schema('task_execution', task_execution_api_schema)
tasks_execution_api_schema = api.schema('tasks_execution', tasks_execution_api_schema)


@execution_api.route('/')
@api.doc(description='Execution ID are held in memory, they will be lost upon daemon restart')
class ExecutionAPI(APIResource):

    @api.response(200, 'list of task executions', tasks_execution_api_schema)
    def get(self, session=None):
        """ List task executions
        List current, pending and previous(hr max) executions
        """
        tasks = [_task_info_dict(task_info) for task_info in self.manager.task_queue.tasks_info.itervalues()]
        return jsonify({"tasks": tasks})

    @api.validate(tasks_execution_api_schema)
    @api.response(400, 'invalid options specified')
    @api.response(200, 'list of tasks queued for execution')
    def post(self, session=None):
        """ Execute task
        Return a unique execution ID for tracking and log streaming
        """
        kwargs = request.json or {}

        options_string = kwargs.pop('options_string', '')
        if options_string:
            try:
                kwargs['options'] = get_parser('execute').parse_args(options_string, raise_errors=True)
            except ValueError as e:
                return {'error': 'invalid options_string specified: %s' % e.message}, 400

        tasks = self.manager.execute(**kwargs)

        return {"tasks": [_task_info_dict(self.manager.task_queue.tasks_info[task_id]) for task_id, event in tasks]}


@api.doc(params={'exec_id': 'Execution ID of the Task'})
@api.doc(description='Execution ID are held in memory, they will be lost upon daemon restart')
@execution_api.route('/<exec_id>/')
class ExecutionTaskAPI(APIResource):

    @api.response(NotFoundError, 'task execution not found')
    @api.response(200, 'list of tasks queued for execution', task_execution_api_schema)
    def get(self, exec_id, session=None):
        """ Status of existing task execution """
        task_info = self.manager.task_queue.tasks_info.get(exec_id)

        if not task_info:
            raise NotFoundError('%s not found' % exec_id)

        return _task_info_dict(task_info)


@api.doc(params={'exec_id': 'Execution ID of the Task'})
@api.doc(description='Execution ID are held in memory, they will be lost upon daemon restart')
@execution_api.route('/<exec_id>/log/')
class ExecutionTaskLogAPI(APIResource):
    @api.response(200, 'Streams as line delimited JSON')
    @api.response(NotFoundError, 'task log not found')
    def get(self, exec_id, session=None):
        """ Log stream of executed task
        Streams as line delimited JSON
        """
        task_info = self.manager.task_queue.tasks_info.get(exec_id)

        if not task_info:
            raise NotFoundError('%s not found' % exec_id)

        def follow():
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

        return Response(follow(), mimetype='text/event-stream')
