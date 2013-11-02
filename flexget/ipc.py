from __future__ import unicode_literals, division, absolute_import
import logging
import threading

import rpyc
from rpyc.utils.server import ThreadedServer

from flexget.scheduler import BufferQueue
from flexget.utils.tools import console

log = logging.getLogger('ipc')

# Allow some attributes from dict interface to be called over the wire
rpyc.core.protocol.DEFAULT_CONFIG['safe_attrs'].update(['items'])


class DaemonService(rpyc.Service):
    # This will be populated when the server is started
    manager = None

    def exposed_execute(self, options=None):
        # Dictionaries are pass by reference with rpyc, turn this into a real dict on our side
        if options:
            options = dict(options.items())
        if self.manager.scheduler.run_queue.qsize() > 0:
            self.client_console('There is already a task executing. This task will execute next.')
        log.info('Executing for client.')
        cron = options and options.get('cron')
        output = None if cron else BufferQueue()
        tasks_finished = self.manager.scheduler.execute(options=options, output=output)
        if output:
            # Send back any output until all tasks have finished
            while any(not t.is_set() for t in tasks_finished):
                try:
                    self.client_console(output.get(True, 0.5).rstrip())
                except BufferQueue.Empty:
                    continue

    def exposed_reload(self):
        # TODO: Reload config
        raise NotImplementedError

    def exposed_shutdown(self, finish_queue=False):
        log.info('Shutdown requested over ipc.')
        self.client_console('Daemon shutdown requested.')
        self.manager.scheduler.shutdown(finish_queue=finish_queue)

    def client_console(self, text):
        self._conn.root.console(text)


class ClientService(rpyc.Service):
    def exposed_console(self, text):
        console(text)


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
