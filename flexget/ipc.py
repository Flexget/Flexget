from __future__ import unicode_literals, division, absolute_import
import argparse
import logging
import socket
from SocketServer import BaseRequestHandler, ThreadingTCPServer
import threading

from flexget.config_schema import process_config
from flexget.scheduler import BufferQueue
from flexget.utils import json
from flexget.utils.tools import console

log = logging.getLogger('ipc')


def remote_execute(port, task, options):
    log.info('Sending task %s to running daemon for execution.' % task)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(None)
    try:
        s.connect(('127.0.0.1', port))
        if isinstance(options, argparse.Namespace):
            options = options.__dict__
            options.pop('__parent__', None)
        s.sendall(json.dumps({'action': 'execute', 'args': {'task': task, 'options': options}}) + '\n')
        for line in s.makefile():
            console(line.decode('utf-8').rstrip())
    except socket.error as e:
        log.error('Socket error while sending execution to daemon: %s' % e)
    except Exception as e:
        log.exception('Unhandled error while sending execution to daemon.')
    finally:
        s.close()


# Used to validate our incoming requests
ipc_message_schema = {
    'type': 'object',
    'properties': {
        'action': {'enum': ['execute', 'reload', 'shutdown']},
        'args': {'type': 'object', 'default': {}}
    },
    'required': ['action'],
    'additionalProperties': False
}


class RequestHandler(BaseRequestHandler):
    def handle(self):
        data = self.request.makefile().readline().decode('utf-8')
        try:
            ipc_message = json.loads(data)
        except ValueError:
            log.error('Error decoding json from ipc message.')
            return
        errors = process_config(ipc_message, ipc_message_schema)
        if errors:
            log.error('Invalid IPC message received.')
            return
        if ipc_message['action'] == 'execute':
            if 'task' not in ipc_message['args']:
                log.error('Task must be specified in execute ipc message')
                return
            self.handle_execute(ipc_message['args']['task'], ipc_message['kwargs'].get('options'))
        elif ipc_message['action'] == 'reload':
            self.handle_reload()
        elif ipc_message == 'shutdown':
            self.handle_shutdown(ipc_message['args'].get('finish_queue', True))

    def handle_execute(self, task, options):
        if self.server.manager.scheduler.run_queue.qsize() > 0:
            self.request.sendall('There is already a task executing. This task will execute next.\n')
        log.info('Executing task `%s` for client at %s.' % (task, self.client_address))
        bufferqueue = BufferQueue()
        self.server.manager.scheduler.execute(task, options=options, output=bufferqueue)
        # If this is a --cron execution, don't stream back the log
        if not options.get('cron'):
            for line in bufferqueue:
                self.request.sendall(line.encode('utf-8'))

    def handle_reload(self):
        # TODO: Reload config
        pass

    def handle_shutdown(self, finish_queue):
        self.server.manager.scheduler.shutdown(finish_queue=finish_queue)
        self.request.sendall('Daemon shutdown requested.')


class IPCServer(threading.Thread):
    def __init__(self, manager, port):
        super(IPCServer, self).__init__(name='ipc_server')
        self.daemon = True
        self.manager = manager
        self.port = port
        self.server = None

    def run(self):
        # Don't actually bind to the port until start is called
        try:
            self.server = ThreadingTCPServer(('127.0.0.1', self.port), RequestHandler)
        except socket.error as e:
            log.critical('IPC server unable to bind to port %s' % self.port)
            log.debug('error', exc_info=True)
            return
        self.server.daemon_threads = True
        self.server.manager = self.manager
        self.manager.write_lock(ipc_port=self.port)
        self.server.serve_forever()

    def shutdown(self):
        if self.server:
            self.server.shutdown()
