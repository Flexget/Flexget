from flask import request, jsonify, Blueprint, Response

import flexget
from flexget.manager import manager
from flexget.options import get_parser
from flexget.ui.options import RaiseErrorArgumentParser
from flexget.ui.executor import BufferQueue

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

    kwargs['output'] = BufferQueue()
    from flexget.ui.webui import executor
    executor.execute(**kwargs)

    def streamer():
        bufferqueue = kwargs['output']
        while True:
            line = bufferqueue.get()
            if line == 'EOF':
                break
            yield line + '\n'

    return Response(streamer(), mimetype='text/plain'), 200


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
