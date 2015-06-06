import logging
import os
from time import sleep
from functools import wraps

from jsonschema.exceptions import RefResolutionError

from flask import Flask, Blueprint, request, jsonify, Response
from flask_restplus import Api as RestPlusAPI
from flask_restplus import swagger
from flask_restplus.resource import Resource
from flask_restplus.model import ApiModel
from flask_restplus.swagger import ref

from flexget import __version__
from flexget.config_schema import process_config
from flexget.manager import manager
from flexget.utils import json
from flexget.utils.database import with_session
from flexget.options import get_parser

API_VERSION = 1

log = logging.getLogger('api')


class ApiSchemaModel(ApiModel):
    def __init__(self, schema, *args, **kwargs):
        self._schema = schema
        super(ApiSchemaModel, self).__init__()

    @property
    def __schema__(self):
        return self._schema


class _Api(RestPlusAPI):

    def schema(self, name, schema, **kwargs):
        """Register a schema"""
        return self.model(name, **kwargs)(ApiSchemaModel(schema))

    def validate(self, model):

        # TODO: Raise error is schema format incorrect
        # I think better to do this in a test. Loop through registered schema models, validate against metaschema

        def decorator(func):

            @api.expect(model)
            @wraps(func)
            def wrapper(*args, **kwargs):
                payload = request.json
                try:
                    errors = process_config(config=payload, schema=model.__schema__)
                    if errors:
                        return {'detail': [error.message for error in errors]}, 400
                except RefResolutionError as e:
                    return {'detail': str(e)}, 400
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

    @api.response(500, 'Error loading the config')
    @api.response(200, 'Reloaded config')
    def get(self, session=None):
        """ Reload Flexget Config """
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
        """ Get server PID """
        return{'pid': os.getpid()}


shutdown_parser = api.parser()
shutdown_parser.add_argument('force', type=bool, required=False, default=False, help='Ignore tasks in the queue')

@server_api.route('/shutdown/')
class ServerShutdownAPI(APIResource):
    @api.doc(parser=shutdown_parser)
    def get(self, session=None):
        """ Shutdown Flexget Daemon """
        args = shutdown_parser.parse_args()
        manager.shutdown(args['force'])
        return {'detail': 'shutdown requested'}


@server_api.route('/config/')
class ServerConfigAPI(APIResource):
    def get(self, session=None):
        """ Get Flexget Config """
        return manager.config


@server_api.route('/version/')
class ServerVersionAPI(APIResource):
    def get(self, session=None):
        """ Flexget Version """
        return {'flexget_version': __version__, 'api_version': API_VERSION}


@server_api.route('/log/')
class ServerLogAPI(APIResource):
    def get(self, session=None):
        """ Stream Flexget log
        Streams as line delimited JSON
        """
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


@execution_api.route('/')
class ExecutionAPI(APIResource):

    def get(self, session=None):
        """ List Task executions
        List current, pending and previous(hr max) executions
        """
        tasks = [_task_info_dict(task_info) for task_info in manager.task_queue.tasks_info.itervalues()]
        return jsonify({"tasks": tasks})

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

        tasks = manager.execute(**kwargs)

        return {"tasks": [_task_info_dict(manager.task_queue.tasks_info[task_id]) for task_id, event in tasks]}


@execution_api.route('/<task_id>/')
class ExecutionTaskAPI(APIResource):

    def execution_by_id(self, task_id, session=None):
        """ Status of existing task execution """
        task_info = manager.task_queue.tasks_info.get(task_id)

        if not task_info:
            return {'detail': '%s not found' % task_id}, 400

        return {'task': _task_info_dict(task_info)}


@execution_api.route('/<task_id>/log/')
class ExecutionTaskLogAPI(APIResource):

    def get(self, task_id, session=None):
        """ Log stream of executed task
        Streams as line delimited JSON
        """
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
        """ Show all tasks """
        tasks = []
        for name in manager.tasks:
            tasks.append({'name': name, 'config': manager.config['tasks'][name]})
        return {'tasks': tasks}

    def post(self):
        """ Add new task """
        # TODO
        return {}


@tasks_api.route('/tasks/<task>/')
@api.doc(params={'task': 'task name'})
class TaskAPI(APIResource):

    def get(self, task, session=None):
        """ Get task config """
        if not task in manager.tasks:
            return {'error': 'task %s not found' % task}, 404

        return {'name': task, 'config': manager.config['tasks'][task]}

    def put(self, task, session=None):
        """ Updates tasks config """
        # TODO: Validate then set
        # TODO: Return 204 if name has been changed
        return {}

    def delete(self, task, session=None):
        """ Delete a task """
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
