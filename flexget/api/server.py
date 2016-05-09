from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import os
import json
import sys
import logging
import threading
import traceback
from time import sleep

import cherrypy
from flask import Response
from flask_restplus import inputs
from pyparsing import Word, Keyword, Group, Forward, Suppress, OneOrMore, oneOf, White, restOfLine, ParseException, \
    Combine
from pyparsing import nums, alphanums, printables

from flexget._version import __version__
from flexget.api import api, APIResource, ApiError, __version__ as __api_version__

log = logging.getLogger('api.server')

server_api = api.namespace('server', description='Manage Daemon')


@server_api.route('/reload/')
class ServerReloadAPI(APIResource):
    @api.response(ApiError, description='Error loading the config')
    @api.response(200, description='Newly reloaded config')
    def get(self, session=None):
        """ Reload Flexget config """
        log.info('Reloading config from disk.')
        try:
            self.manager.load_config()
        except ValueError as e:
            raise ApiError('Error loading config: %s' % e.args[0])

        log.info('Config successfully reloaded from disk.')
        return {}


pid_schema = api.schema('server.pid', {
    'type': 'object',
    'properties': {
        'pid': {
            'type': 'integer'
        }
    }
})


@server_api.route('/pid/')
class ServerPIDAPI(APIResource):
    @api.response(200, description='Reloaded config', model=pid_schema)
    def get(self, session=None):
        """ Get server PID """
        return {'pid': os.getpid()}


shutdown_parser = api.parser()
shutdown_parser.add_argument('force', type=inputs.boolean, required=False, default=False,
                             help='Ignore tasks in the queue')


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
    @api.response(200, description='Flexget config')
    def get(self, session=None):
        """ Get Flexget Config """
        return self.manager.config


version_schema = api.schema('server.version', {
    'type': 'object',
    'properties': {
        'flexget_version': {'type': 'string'},
        'api_version': {'type': 'integer'}
    }
})


@server_api.route('/version/')
class ServerVersionAPI(APIResource):
    @api.response(200, description='Flexget version', model=version_schema)
    def get(self, session=None):
        """ Flexget Version """
        return {'flexget_version': __version__, 'api_version': __api_version__}


dump_threads_schema = api.schema('server.dump_threads', {
    'type': 'object',
    'properties': {
        'threads': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'id': {'type': 'string'},
                    'dump': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    }
                },
            },
        }
    }
})


@server_api.route('/dump_threads/')
class ServerDumpThreads(APIResource):
    @api.response(200, description='Flexget threads dump', model=dump_threads_schema)
    def get(self, session=None):
        """ Dump Server threads for debugging """
        id2name = dict([(th.ident, th.name) for th in threading.enumerate()])
        threads = []
        for threadId, stack in sys._current_frames().items():
            dump = []
            for filename, lineno, name, line in traceback.extract_stack(stack):
                dump.append('File: "%s", line %d, in %s' % (filename, lineno, name))
                if line:
                    dump.append(line.strip())
            threads.append({
                'name': id2name.get(threadId),
                'id': threadId,
                'dump': dump
            })

        return {'threads': threads}


server_log_parser = api.parser()
server_log_parser.add_argument(
    'lines', type=int, required=False, default=200,
    help='How many lines to find before streaming'
)
server_log_parser.add_argument('search', type=str, required=False, help='Search filter support google like syntax')


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
        lines = buf.decode(sys.getfilesystemencoding()).split('\n')
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


def file_inode(filename):
    try:
        fd = os.open(filename, os.O_RDONLY)
        inode = os.fstat(fd).st_ino
        return inode
    except OSError:
        return 0
    finally:
        if fd:
            os.close(fd)


@server_api.route('/log/')
class ServerLogAPI(APIResource):
    @api.doc(parser=server_log_parser)
    @api.response(200, description='Streams as line delimited JSON')
    def get(self, session=None):
        """ Stream Flexget log Streams as line delimited JSON """
        args = server_log_parser.parse_args()

        def follow(lines, search):
            log_parser = LogParser(search)
            stream_from_byte = 0

            lines_found = []

            if os.path.isabs(self.manager.options.logfile):
                base_log_file = self.manager.options.logfile
            else:
                base_log_file = os.path.join(self.manager.config_base, self.manager.options.logfile)

            yield '{"stream": ['  # Start of the json stream

            # Read back in the logs until we find enough lines
            for i in range(0, 9):
                log_file = ('%s.%s' % (base_log_file, i)).rstrip('.0')  # 1st log file has no number

                if not os.path.isfile(log_file):
                    break

                with open(log_file, 'rb') as fh:
                    fh.seek(0, 2)  # Seek to bottom of file
                    end_byte = fh.tell()
                    if i == 0:
                        stream_from_byte = end_byte  # Stream from this point later on

                    if len(lines_found) >= lines:
                        break

                    # Read in reverse for efficiency
                    for line in reverse_readline(fh, start_byte=end_byte):
                        if len(lines_found) >= lines:
                            break
                        if log_parser.matches(line):
                            lines_found.append(log_parser.json_string(line))

                    for l in reversed(lines_found):
                        yield l + ',\n'

            # We need to track the inode in case the log file is rotated
            current_inode = file_inode(base_log_file)

            while True:
                # If the server is shutting down then end the stream nicely
                if cherrypy.engine.state != cherrypy.engine.states.STARTED:
                    break

                new_inode = file_inode(base_log_file)
                if current_inode != new_inode:
                    # File updated/rotated. Read from beginning
                    stream_from_byte = 0
                    current_inode = new_inode

                try:
                    with open(base_log_file, 'rb') as fh:
                        fh.seek(stream_from_byte)
                        line = fh.readline().decode(sys.getfilesystemencoding())
                        stream_from_byte = fh.tell()
                except IOError:
                    yield '{}'
                    continue

                # If a valid line is found and does not pass the filter then set it to none
                line = log_parser.json_string(line) if log_parser.matches(line) else '{}'

                if line == '{}':
                    # If no match then delay to prevent many read hits on the file
                    sleep(2)

                yield line + ',\n'

            yield '{}]}'  # End of stream

        return Response(follow(args['lines'], args['search']), mimetype='text/event-stream')


class LogParser(object):
    """
    Filter log file.

    Supports
      * 'and', 'or' and implicit 'and' operators;
      * parentheses;
      * quoted strings;
    """

    def __init__(self, query):
        self._methods = {
            'and': self.evaluate_and,
            'or': self.evaluate_or,
            'not': self.evaluate_not,
            'parenthesis': self.evaluate_parenthesis,
            'quotes': self.evaluate_quotes,
            'word': self.evaluate_word,
        }

        self.line = ''
        self.query = query.lower() if query else ''

        if self.query:
            # TODO: Cleanup
            operator_or = Forward()
            operator_word = Group(Word(alphanums)).setResultsName('word')

            operator_quotes_content = Forward()
            operator_quotes_content << (
                (operator_word + operator_quotes_content) | operator_word
            )

            operator_quotes = Group(
                Suppress('"') + operator_quotes_content + Suppress('"')
            ).setResultsName('quotes') | operator_word

            operator_parenthesis = Group(
                (Suppress('(') + operator_or + Suppress(")"))
            ).setResultsName('parenthesis') | operator_quotes

            operator_not = Forward()
            operator_not << (Group(
                Suppress(Keyword('no', caseless=True)) + operator_not
            ).setResultsName('not') | operator_parenthesis)

            operator_and = Forward()
            operator_and << (Group(
                operator_not + Suppress(Keyword('and', caseless=True)) + operator_and
            ).setResultsName('and') | Group(
                operator_not + OneOrMore(~oneOf('and or') + operator_and)
            ).setResultsName('and') | operator_not)

            operator_or << (Group(
                operator_and + Suppress(Keyword('or', caseless=True)) + operator_or
            ).setResultsName('or') | operator_and)

            self._query_parser = operator_or.parseString(self.query)[0]
        else:
            self._query_parser = False

        time_cmpnt = Word(nums).setParseAction(lambda t: t[0].zfill(2))
        date = Combine((time_cmpnt + '-' + time_cmpnt + '-' + time_cmpnt) + ' ' + time_cmpnt + ':' + time_cmpnt)
        word = Word(printables)

        self._log_parser = (
            date.setResultsName('timestamp') +
            word.setResultsName('log_level') +
            word.setResultsName('plugin') +
            (
                White(min=16).setParseAction(lambda s, l, t: [t[0].strip()]).setResultsName('task') |
                (White(min=1).suppress() & word.setResultsName('task'))
            ) +
            restOfLine.setResultsName('message')
        )

    def evaluate_and(self, argument):
        return self.evaluate(argument[0]) and self.evaluate(argument[1])

    def evaluate_or(self, argument):
        return self.evaluate(argument[0]) or self.evaluate(argument[1])

    def evaluate_not(self, argument):
        return not self.evaluate(argument[0])

    def evaluate_parenthesis(self, argument):
        return self.evaluate(argument[0])

    def evaluate_quotes(self, argument):
        search_terms = [term[0] for term in argument]
        return ' '.join(search_terms) in ' '.join(self.line.split())

    def evaluate_word(self, argument):
        return argument[0] in self.line

    def evaluate(self, argument):
        return self._methods[argument.getName()](argument)

    def matches(self, line):
        if not line:
            return False

        self.line = line.lower()

        if not self._query_parser:
            return True
        else:
            return self.evaluate(self._query_parser)

    def json_string(self, line):
        try:
            return json.dumps(self._log_parser().parseString(line).asDict())
        except ParseException:
            return '{}'
