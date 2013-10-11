from __future__ import unicode_literals, division, absolute_import
import argparse
import contextlib
import logging
import socket
import threading
import time

from flexget.scheduler import BufferQueue
from flexget.utils import json
from flexget.utils.tools import console

log = logging.getLogger('ipc')


def remote_execute(port, task, options):
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


class IPCServer(threading.Thread):
    def __init__(self, manager, port):
        super(IPCServer, self).__init__()
        self.daemon = True
        self.manager = manager
        self.host = '127.0.0.1'
        self.port = port
        self._shutdown = False

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((self.host, self.port))
        except socket.error as e:
            log.error('Error binding to socket %s' % e)
            return
        while not self._shutdown:
            try:
                s.settimeout(None)
                s.listen(1)
                conn, addr = s.accept()
                conn.settimeout(60)
                with contextlib.closing(conn) as conn:
                    buffer = b''
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            log.error('Connection with client ended prematurely.')
                            continue
                        buffer += data
                        if b'\n' in data:
                            break
                    try:
                        args = json.loads(buffer)
                    except ValueError:
                        log.error('Error decoding ipc message.')
                        continue
                    bufferqueue = BufferQueue()
                    if self.manager.scheduler.run_queue.qsize() > 0:
                        conn.sendall('There is already a task executing. This task will execute next.\n')
                    log.info('Executing task `%s` for client at %s.' % (args['task'], addr))
                    self.manager.scheduler.execute(args['task'], options=args['options'], output=bufferqueue)
                    for line in bufferqueue:
                        conn.sendall(line.encode('utf-8'))
            except socket.error as e:
                log.error('Socket error while communicating with client: %s' % e)
            except Exception as e:
                log.exception('Unhandled exception while communicating with client.')

    def shutdown(self):
        self._shutdown = True
