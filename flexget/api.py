import logging
import os
from time import sleep
from functools import wraps

import flexget
from flask import Flask, Blueprint, request, jsonify, Response
from flask_restplus import Api as RestPlusAPI
from flask_restplus import swagger
from flask_restplus.resource import Resource
from flask_restplus import fields

from flexget.manager import manager
from flexget.utils import json
from flexget.utils.database import with_session
from flexget.options import get_parser

API_VERSION = 1

log = logging.getLogger('api')

class Swagger(swagger.Swagger):
    def serialize_schema(self, model):
        if isinstance(model, dict):
            return model
        return swagger.Swagger.serialize_schema(self, model)


class _Api(RestPlusAPI):

    def swagger_view(self):
        class SwaggerView(Resource):
            api = self

            def get(self):
                return Swagger(self.api).as_dict()

            def mediatypes(self):
                return ['application/json']
        return SwaggerView

    def expect(self, schema):
        # Add doc here

        def decorator(func):
            @api.doc(body=schema)
            @wraps(func)
            def wrapper(*args, **kwargs):
                # TODO: Validate Schema here
                return func(*args, **kwargs)
            return wrapper
        return decorator


api_bp = Blueprint('api', __name__, url_prefix='/api')
api = _Api(api_bp, catch_all_404s=True, title='Flexget API')


class APIResource(Resource):
    method_decorators = [with_session]


# Server API
server_api = api.namespace('server', description='Manage Flexget Server')


@server_api.route('/reload/')
class ServerReloadAPI(APIResource):
    def post(self, session=None):
        log.info('Reloading config from disk.')
        try:
            manager.load_config()
        except ValueError as e:
            return {'detail': 'Error loading config %s' % e.args[0]}, 500

        log.info('Config successfully reloaded from disk.')
        return {'detail': 'Config successfully reloaded from disk.'}


@server_api.route('/pid/')
class ServerPIDAPI(APIResource):
    def get(self, session=None):
        return{'pid': os.getpid()}


@server_api.route('/shutdown/')
class ServerShutdownAPI(APIResource):
    def get(self, session=None):
        data = request.json if request.json else {}
        force = data.get('force', False)
        manager.shutdown(force)
        return {'detail': 'shutdown requested'}


@server_api.route('/config/')
class ServerConfigAPI(APIResource):
    def get(self, session=None):
        return manager.config


@server_api.route('/version/')
class ServerVersionAPI(APIResource):
    def get(self, session=None):
        return {'flexget_version': flexget.__version__, 'api_version': API_VERSION}


@server_api.route('/log/')
class ServerLogAPI(APIResource):
    def get(self, session=None):
        def tail():
            f = open(os.path.join(manager.config_base, 'log-%s.json' % manager.config_name), 'r')
            while True:
                line = f.readline()
                if not line:
                    sleep(0.1)
                    continue
                yield line

        return Response(tail(), mimetype='text/event-stream')


# Execution API
execution_api = api.namespace('execution', description='Execute tasks')


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


execute_post_schema = {
    "type": "object",
    "properties": {
        "options": {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                }
            },
            "required": ["tasks"]
        }
    },
    "required": ["options"]
}

@execution_api.route('/')
class ExecutionAPI(APIResource):

    def get(self, session=None):
        tasks = [_task_info_dict(task_info) for task_info in manager.task_queue.tasks_info.itervalues()]
        return jsonify({"tasks": tasks})

    @api.expect(execute_post_schema)
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


@execution_api.route('/<task_id>/')
class ExecutionTaskAPI(APIResource):

    def execution_by_id(self, task_id, session=None):
        task_info = manager.task_queue.tasks_info.get(task_id)

        if not task_info:
            return {'detail': '%s not found' % task_id}, 400

        return {'task': _task_info_dict(task_info)}


@execution_api.route('/<task_id>/log/')
class ExecutionTaskLogAPI(APIResource):

    def get(self, task_id, session=None):
        task_info = manager.task_queue.tasks_info.get(task_id)

        if not task_info:
            return {'detail': '%s not found' % task_id}, 400

        def follow():
            f = open(os.path.join(manager.config_base, 'log-%s.json' % manager.config_name), 'r')
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


# Tasks API
tasks_api = api.namespace('tasks', description='Manage Tasks')


@tasks_api.route('/')
class TasksAPI(APIResource):

    def get(self, session=None):
        tasks = []
        for name in manager.tasks:
            tasks.append({'name': name, 'config': manager.config['tasks'][name]})
        return {'tasks': tasks}

    def post(self):
        # TODO
        return {}


@tasks_api.route('/tasks/<task>/')
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
        try:
            manager.config['tasks'].pop(task)
        except KeyError:
            return {'detail': 'invalid task'}, 404

        return {'detail': 'deleted'}


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