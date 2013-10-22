from __future__ import unicode_literals, division, absolute_import
import logging
import sys
import threading

import rpyc
from rpyc.utils.server import ThreadedServer

from flexget.scheduler import BufferQueue
from flexget.utils.tools import console

log = logging.getLogger('ipc')

# Allow some attributes from dict and file interface to be called over the wire
rpyc.core.protocol.DEFAULT_CONFIG['safe_attrs'].update(['items', 'write', 'flush'])


class DaemonService(rpyc.Service):
    # This will be populated when the server is started
    manager = None

    def exposed_execute(self, task, options=None):
        # Dictionaries are pass by reference with rpyc, turn this into a real dict on our side
        if options:
            options = dict(options.items())
        if self.manager.scheduler.run_queue.qsize() > 0:
            self._conn.root.console('There is already a task executing. This task will execute next.')
        log.info('Executing task `%s` for client.' % task)
        cron = options and options.get('cron')
        output = None if cron else self._conn.root.get_stdout()
        task_finished = self.manager.scheduler.execute(task, options=options, output=output)
        if not cron:
            # Wait until task has finished so that log is sent back
            task_finished.wait()

    def exposed_reload(self):
        # TODO: Reload config
        raise NotImplementedError

    def exposed_shutdown(self, finish_queue):
        self.manager.scheduler.shutdown(finish_queue=finish_queue)
        self._conn.root.console('Daemon shutdown requested.')


class ClientService(rpyc.Service):
    def exposed_get_stdout(self):
        """Let the daemon write to our stdout"""
        return sys.stdout


class IPCServer(threading.Thread):
    def __init__(self, manager, port):
        super(IPCServer, self).__init__(name='ipc_server')
        self.daemon = True
        self.manager = manager
        self.host = "127.0.0.1"
        self.port = port
        self.server = None

    def run(self):
        DaemonService.manager = self.manager
        self.server = ThreadedServer(DaemonService, hostname=self.host, port=self.port)
        self.manager.write_lock(ipc_port=self.port)
        self.server.start()

    def shutdown(self):
        self.server.close()


class IPCClient(object):
    def __init__(self, port):
        self.conn = rpyc.connect("127.0.0.1", port, service=ClientService)

    def close(self):
        self.conn.close()

    def __getattr__(self, item):
        """Proxy all other calls to the exposed daemon service."""
        return getattr(self.conn.root, item)
