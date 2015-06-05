from flask import request, Blueprint, Response, Flask
import flask_restful

import os
from time import sleep

import flexget
from flexget.manager import manager
from flexget.options import get_parser
from flexget.utils import json
from flexget.utils.database import with_session

API_VERSION = 1

api_bp = Blueprint('api', __name__, url_prefix='/api')
api = flask_restful.Api(api_bp, catch_all_404s=True)

json_log = os.path.join(manager.config_base, 'log-%s.json' % manager.config_name)

class APIResource(flask_restful.Resource):
    method_decorators = [with_session]


# Version API
class VersionAPI(APIResource):

    def get(self, session=None):
        return {'flexget_version': flexget.__version__, 'api_version': API_VERSION}

api.add_resource(VersionAPI, '/version/ ')


# Execution API
def _task_info_dict(task_info):
    return {
        'id': task_info.id,
        'name': task_info.name,
        'status': task_info.status,
        'created': task_info.created,
        'started': task_info.started,
        'finished': task_info.finished,
        'message': task_info.message,
        'log': {'href': '/execution/%s/log/' % task_info.id},
    }


class ExecutionAPI(APIResource):

    def get(self, session=None):
        tasks = [_task_info_dict(task_info) for task_info in manager.task_queue.tasks_info.itervalues()]
        return {"tasks": tasks}

    def post(self, session=None):
        kwargs = request.json or {}

        options_string = kwargs.pop('options_string', '')
        if options_string:
            try:
                kwargs['options'] = get_parser('execute').parse_args(options_string, raise_errors=True)
            except ValueError as e:
                return {'error': 'invalid options_string specified: %s' % e.message}, 400

        tasks = manager.execute(**kwargs)

        return {"tasks": [_task_info_dict(manager.task_queue.tasks_info[task_id]) for task_id, event in tasks]}


class ExecutionTaskAPI(APIResource):

    def execution_by_id(self, task_id, session=None):
        task_info = manager.task_queue.tasks_info.get(task_id)

        if not task_info:
            return {'detail': '%s not found' % task_id}, 400

        return {'task': _task_info_dict(task_info)}


class ExecutionLogAPI(APIResource):

    def get(self, session=None):
        def tail():
            f = open(json_log, 'r')
            while True:
                line = f.readline()
                if not line:
                    sleep(0.1)
                    continue
                yield line

        return Response(tail(), mimetype='text/event-stream')


class ExecutionTaskLogAPI(APIResource):

    def get(self, task_id, session=None):
        task_info = manager.task_queue.tasks_info.get(task_id)

        if not task_info:
            return {'detail': '%s not found' % task_id}, 400

        def follow():
            f = open(json_log, 'r')
            while True:
                if not task_info.started:
                    continue

                # First check if it has finished, if there is no new lines then we can return
                finished = task_info.finished is not None
                line = f.readline()
                if not line:
                    if finished:
                        return
                    sleep(0.1)
                    continue

                record = json.loads(line)
                if record['task_id'] != task_id:
                    continue
                yield line

        return Response(follow(), mimetype='text/event-stream')

api.add_resource(ExecutionAPI, '/execution/')
api.add_resource(ExecutionLogAPI, '/execution/log/')
api.add_resource(ExecutionTaskAPI, '/execution/<task_id>/')
api.add_resource(ExecutionTaskLogAPI, '/execution/<task_id>/log/')


class TasksAPI(APIResource):

    def get(self, session=None):
        tasks = []
        for name in manager.tasks:
            tasks.append({'name': name, 'config': manager.config['tasks'][name]})
        return {'tasks': tasks}

    def post(self):
        # TODO
        return {}


class TaskAPI(APIResource):

    def get(self, task, session=None):
        if not task in manager.tasks:
            return {'error': 'task %s not found' % task}, 404

        return {'name': task, 'config': manager.config['tasks'][task]}

    def put(self, task, session=None):
        # TODO: Validate then set
        # TODO: Return 204 if name has been changed
        return {}

    def delete(self, task, session=None):
        manager.config['tasks'].pop(task)
        return {'detail': 'deleted'}


api.add_resource(TasksAPI, '/tasks/')
api.add_resource(TaskAPI, '/tasks/<task>/')


class ConfigAPI(APIResource):

    def get(self):
        return manager.config


api.add_resource(ConfigAPI, '/config/')


class ApiClient(object):
    """
    This is an client which can be used as a more pythonic interface to the rest api.

    It skips http, and is only usable from within the running flexget process.
    """
    def __init__(self):
        app = Flask(__name__)
        app.register_blueprint(api)
        self.app = app.test_client()

    def __getattr__(self, item):
        return ApiEndopint('/api/' + item, self.get_endpoint)

    def get_endpoint(self, url, data, method=None):
        if method is None:
            method = 'POST' if data is not None else 'GET'
        response = self.app.open(url, data=data, follow_redirects=True, method=method)
        result = json.loads(response.data)
        # TODO: Proper exceptions
        if 200 > response.status_code >= 300:
            raise Exception(result['error'])
        return result


class ApiEndopint(object):
    def __init__(self, endpoint, caller):
        self.endpoint = endpoint
        self.caller = caller

    def __getattr__(self, item):
        return self.__class__(self.endpoint + '/' + item, self.caller)

    __getitem__ = __getattr__

    def __call__(self, data=None, method=None):
        return self.caller(self.endpoint, data=data, method=method)