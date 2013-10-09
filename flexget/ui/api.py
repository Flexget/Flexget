from flask import request, jsonify, Blueprint, Response, flash

import flexget
from flexget.config_schema import resolve_ref, process_config, get_schema
from flexget.manager import manager
from flexget.options import get_parser, RaiseErrorArgumentParser
from flexget.plugin import plugin_schemas
from flexget.scheduler import BufferQueue

API_VERSION = 1

api = Blueprint('api', __name__, url_prefix='/api')

exec_parser = RaiseErrorArgumentParser(parents=[get_parser('execute')])


# TODO: These endpoints should probably return a header which points to a json schema describing the return data
@api.route('/version')
def version():
    return jsonify(flexget_version=flexget.__version__, api_version=API_VERSION)


@api.route('/execute', methods=['GET', 'POST'])
def execute():
    kwargs = request.json or {}
    options_string = kwargs.pop('options_string', '')
    if options_string:
        try:
            kwargs['options'] = exec_parser.parse_args(options_string)
        except ValueError as e:
            return jsonify(error='invalid options_string specified: %s' % e.message), 400

    # We'll stream the log results as they arrive in the bufferqueue
    kwargs['output'] = BufferQueue()
    manager.scheduler.execute(**kwargs)

    return Response(kwargs['output'], mimetype='text/plain'), 200


# TODO: return proper schemas in headers, also none of these should allow setting invalid config
@api.route('/config', methods=['GET', 'PUT'])
def config_root():
    return jsonify(manager.config)


@api.route('/config/<section>', methods=['GET', 'PUT', 'DELETE'])
def config_section(section):
    if request.method == 'GET':
        return jsonify(manager.config[section])
    elif request.method == 'PUT':
        manager.config[section] = request.json
    elif request.method == 'DELETE':
        del manager.config[section]


@api.route('/config/tasks/<taskname>', methods=['GET', 'PUT', 'DELETE'])
def config_tasks(taskname):
    if request.method != 'PUT':
        if taskname not in manager.config['tasks']:
            return jsonify(error='Requested task does not exist'), 404
    status_code = 200
    if request.method == 'PUT':
        if 'rename' in request.args:
            pass  # TODO: Rename the task, return 204 with new location header
        if taskname not in manager.config['tasks']:
            status_code = 201
        manager.config['tasks'][taskname] = request.json
    elif request.method == 'DELETE':
        del manager.config['tasks'][taskname]
        return Response(status=204)
    return jsonify(manager.config['tasks'][taskname]), status_code

@api.route('/config/<root_key>', methods=['GET', 'PUT', 'DELETE'])
def config_root_key(root_key):
    if request.method == 'PUT':
        schema = resolve_ref('/schema/config/%s' % root_key)
        errors = process_config(request.json, schema, set_defaults=False)
        if errors:
            return jsonify({'$errors': errors}), 400
        manager.config[root_key] = request.json
    if root_key not in manager.config:
        return 'Not found', 404
    response = jsonify(manager.config[root_key])
    response.headers[b'Content-Type'] += '; profile=/schema/config/%s' % root_key
    return response


# Serves the appropriate schema for any /api method. Schema for /api/x/y can be found at /schema/api/x/y
api_schema = Blueprint('api_schema', __name__, url_prefix='/schema/api')

@api_schema.route('/config')
def cs_root():
    return get_schema()


@api_schema.route('/config/<root_key>')
def cs_tasks(root_key):
    root_schema = get_schema()
    if root_key not in root_schema['properties']:
        return 'Not found', 404
    return root_schema['properties'][root_key]


@api_schema.route('/config/templates/<name>', defaults={'section': 'templates'})
@api_schema.route('/config/tasks/<name>', defaults={'section': 'tasks'})
def cs_plugin_container(section, name):
    hyper_schema = {
        'links': [
            {'rel': 'self', 'href': request.path}
        ]
    }

    return plugin_schemas(context='task')
