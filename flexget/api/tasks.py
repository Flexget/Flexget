import copy

from flask import request

from flexget.config_schema import process_config
from flexget.api import api, APIResource, ApiError, NotFoundError


# Tasks API
tasks_api = api.namespace('tasks', description='Manage Tasks')

task_api_schema = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'config': {'$ref': '/schema/plugins'}
    },
    'additionalProperties': False
}

tasks_api_schema = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": task_api_schema
        }
    },
    'additionalProperties': False
}

tasks_api_schema = api.schema('tasks', tasks_api_schema)
task_api_schema = api.schema('task', task_api_schema)


@tasks_api.route('/')
class TasksAPI(APIResource):

    @api.response(200, 'list of tasks', tasks_api_schema)
    def get(self, session=None):
        """ Show all tasks """

        tasks = []
        for name, config in self.manager.user_config.get('tasks', {}).iteritems():
            tasks.append({'name': name, 'config': config})
        return {'tasks': tasks}

    @api.validate(task_api_schema)
    @api.response(201, 'newly created task', task_api_schema)
    @api.response(409, 'task already exists', task_api_schema)
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
@api.doc(params={'task': 'task name'})
class TaskAPI(APIResource):

    @api.response(200, 'task config', task_api_schema)
    @api.response(NotFoundError, 'task not found')
    @api.response(ApiError, 'unable to read config')
    def get(self, task, session=None):
        """ Get task config """
        if task not in self.manager.user_config.get('tasks', {}):
            raise NotFoundError('task `%s` not found' % task)

        return {'name': task, 'config': self.manager.user_config['tasks'][task]}

    @api.validate(task_api_schema)
    @api.response(200, 'updated task', task_api_schema)
    @api.response(201, 'renamed task', task_api_schema)
    @api.response(404, 'task does not exist', task_api_schema)
    @api.response(400, 'cannot rename task as it already exist', task_api_schema)
    def post(self, task, session=None):
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

    @api.response(200, 'deleted task')
    @api.response(404, 'task not found')
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
