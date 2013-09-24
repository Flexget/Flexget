from flask import request, jsonify, Blueprint, Response

import flexget
from flexget.options import CoreArgumentParser
from flexget.ui.options import RaiseErrorArgumentParser
from flexget.ui.executor import BufferQueue

API_VERSION = 1

api = Blueprint('api', __name__, url_prefix='/api')

exec_parser = RaiseErrorArgumentParser(parents=[CoreArgumentParser().get_subparser('execute')])


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

