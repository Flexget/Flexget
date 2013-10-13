from __future__ import unicode_literals, division, absolute_import
import argparse
import logging
import socket
from SocketServer import BaseRequestHandler, ThreadingTCPServer
import threading

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
        s.sendall(json.dumps({'task': task, 'options': options}) + '\n')
        for line in s.makefile():
            console(line.decode('utf-8').rstrip())
    except socket.error as e:
        log.error('Socket error while sending execution to daemon: %s' % e)
    except Exception as e:
        log.exception('Unhandled error while sending execution to daemone.')
    finally:
        s.close()


class RequestHandler(BaseRequestHandler):
    def handle(self):
        data = self.request.makefile().readline().decode('utf-8')
        try:
            args = json.loads(data)
        except ValueError:
            log.error('Error decoding ipc message.')
            return
        bufferqueue = BufferQueue()
        if self.server.manager.scheduler.run_queue.qsize() > 0:
            self.request.sendall('There is already a task executing. This task will execute next.\n')
        log.info('Executing task `%s` for client at %s.' % (args['task'], self.client_address))
        self.server.manager.scheduler.execute(args['task'], options=args['options'], output=bufferqueue)
        for line in bufferqueue:
            self.request.sendall(line.encode('utf-8'))


class IPCServer(threading.Thread):
    def __init__(self, manager, port):
        super(IPCServer, self).__init__(name='ipc_server')
        self.daemon = True
        self.manager = manager
        self.port = port
        self.server = None

    def run(self):
        # Don't actually bind to the port until start is called
        self.server = ThreadingTCPServer(('127.0.0.1', self.port), RequestHandler)
        self.server.daemon_threads = True
        self.server.manager = self.manager
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()
