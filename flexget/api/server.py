import os
import logging
from time import sleep

from flask import Response

from flexget.api import api, APIResource, ApiError, __version__ as __api_version__
from flexget.utils import json
from flexget._version import __version__

log = logging.getLogger('api.server')

server_api = api.namespace('server', description='Manage Flexget Daemon')


@server_api.route('/reload/')
class ServerReloadAPI(APIResource):

    @api.response(ApiError, 'Error loading the config')
    @api.response(200, 'Reloaded config')
    def get(self, session=None):
        """ Reload Flexget config """
        log.info('Reloading config from disk.')
        try:
            self.manager.load_config()
        except ValueError as e:
            raise ApiError('Error loading config: %s' % e.args[0])

        log.info('Config successfully reloaded from disk.')
        return {}


pid_schema = api.schema('server_pid', {
    'type': 'object',
    'properties': {
        'pid': {
            'type': 'integer'
        }
    }
})


@server_api.route('/pid/')
class ServerPIDAPI(APIResource):
    @api.response(200, 'Reloaded config', pid_schema)
    def get(self, session=None):
        """ Get server PID """
        return{'pid': os.getpid()}


shutdown_parser = api.parser()
shutdown_parser.add_argument('force', type=bool, required=False, default=False, help='Ignore tasks in the queue')


@server_api.route('/shutdown/')
class ServerShutdownAPI(APIResource):
    @api.doc(parser=shutdown_parser)
    @api.response(200, 'Shutdown requested')
    def get(self, session=None):
        """ Shutdown Flexget Daemon """
        args = shutdown_parser.parse_args()
        self.manager.shutdown(args['force'])
        return {}


@server_api.route('/config/')
class ServerConfigAPI(APIResource):
    @api.response(200, 'Flexget config')
    def get(self, session=None):
        """ Get Flexget Config """
        return self.manager.config


version_schema = api.schema('version', {
    'type': 'object',
    'properties': {
        'flexget_version': {'type': 'string'},
        'api_version': {'type': 'integer'}
    }
})


@server_api.route('/version/')
class ServerVersionAPI(APIResource):
    @api.response(200, 'Flexget version', version_schema)
    def get(self, session=None):
        """ Flexget Version """
        return {'flexget_version': __version__, 'api_version': __api_version__}


server_log_parser = api.parser()
server_log_parser.add_argument(
    'lines', type=int, required=False, default=200,
    help='How many lines to find before streaming'
)

log_filter_fields = ['message', 'task', 'asctime', 'levelname', 'name']
for field in log_filter_fields:
    server_log_parser.add_argument(field, type=str, required=False, help='Filter by %s' % field)


def reverse_readline(fh, start_byte=0, buf_size=8192):
    """a generator that returns the lines of a file in reverse order"""
    segment = None
    offset = 0
    if start_byte:
        fh.seek(start_byte)
    else:
        fh.seek(0, os.SEEK_END)
    total_size = remaining_size = fh.tell()
    while remaining_size > 0:
        offset = min(total_size, offset + buf_size)
        fh.seek(-offset, os.SEEK_END)
        buf = fh.read(min(remaining_size, buf_size))
        remaining_size -= buf_size
        lines = buf.split('\n')
        # the first line of the buffer is probably not a complete line so
        # we'll save it and append it to the last line of the next buffer
        # we read
        if segment is not None:
            # if the previous chunk starts right from the beginning of line
            # do not concact the segment to the last line of new chunk
            # instead, yield the segment first
            if buf[-1] is not '\n':
                lines[-1] += segment
            else:
                yield segment
        segment = lines[0]
        for index in range(len(lines) - 1, 0, -1):
            if len(lines[index]):
                yield lines[index]
    yield segment


@server_api.route('/log/')
class ServerLogAPI(APIResource):

    @api.doc(parser=server_log_parser)
    @api.response(200, 'Streams as line delimited JSON')
    def get(self, session=None):
        """ Stream Flexget log Streams as line delimited JSON """
        args = server_log_parser.parse_args()

        def line_filter(line, fields):
            line = json.loads(line)

            if not line:
                return False

            for f, filter_str in fields.iteritems():
                if not filter_str or f not in line:
                    continue

                if f == 'levelname':
                    line_level = logging.getLevelName(line['levelname'])
                    try:
                        filter_level = int(filter_str)
                    except ValueError:
                        filter_level = logging.getLevelName(filter_str.upper())

                    if line_level < filter_level:
                        return False
                    else:
                        continue

                if filter_str.lower() not in line.get(f, '').lower():
                    return False
            return True

        def follow(lines, fields_filter={}):
            with open(os.path.join(self.manager.config_base, 'log-%s.json' % self.manager.config_name), 'rb') as fh:
                # Before streaming return existing log lines
                fh.seek(0, 2)
                stream_from_byte = fh.tell()

                lines_found = []
                # Read in reverse for efficiency
                for line in reverse_readline(fh, start_byte=stream_from_byte):
                    if len(lines_found) >= lines:
                        break
                    if line_filter(line, fields_filter):
                        lines_found.append(line)

                for l in reversed(lines_found):
                    yield l

                fh.seek(stream_from_byte)
                while True:
                    line = fh.readline()

                    # If a valid line is found and does not pass the filter then set it to none
                    if line and not line_filter(line, fields_filter):
                        line = None

                    if not line:
                        # If line is empty then delay and send an empty line to flask can ensure the client is alive
                        line = '{}'
                        sleep(0.5)
                    yield line

        max_lines = args['lines']
        del args['lines']

        return Response(follow(max_lines, args), mimetype='text/event-stream')
