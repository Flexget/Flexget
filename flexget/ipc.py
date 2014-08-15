from __future__ import unicode_literals, division, absolute_import
import logging
import random
import string
import threading

import rpyc
from rpyc.utils.server import ThreadedServer

from flexget.utils.tools import BufferQueue, console

log = logging.getLogger('ipc')

# Allow some attributes from dict interface to be called over the wire
rpyc.core.protocol.DEFAULT_CONFIG['safe_attrs'].update(['items'])
rpyc.core.protocol.DEFAULT_CONFIG['allow_pickle'] = True

IPC_VERSION = 1
AUTH_ERROR = 'authentication error'
AUTH_SUCCESS = 'authentication success'


class DaemonService(rpyc.Service):
    # This will be populated when the server is started
    manager = None

    def exposed_version(self):
        return IPC_VERSION

    def exposed_execute(self, options=None):
        # Dictionaries are pass by reference with rpyc, turn this into a real dict on our side
        if options:
            options = rpyc.utils.classic.obtain(options)
        if len(self.manager.task_queue) > 0:
            self.client_console('There is already a task executing. This task will execute next.')
        log.info('Executing for client.')
        cron = options and options.get('cron')
        output = None if cron else BufferQueue()
        tasks_finished = self.manager.execute(options=options, output=output)
        if output:
            # Send back any output until all tasks have finished
            while any(not t.is_set() for t in tasks_finished) or output.qsize():
                try:
                    self.client_console(output.get(True, 0.5).rstrip())
                except BufferQueue.Empty:
                    continue

    def exposed_reload(self):
        try:
            self.manager.load_config()
        except ValueError as e:
            self.client_console('Error loading config: %s' % e.args[0])
        else:
            self.client_console('Config successfully reloaded from disk.')

    def exposed_shutdown(self, finish_queue=False):
        log.info('Shutdown requested over ipc.')
        self.client_console('Daemon shutdown requested.')
        self.manager.shutdown(finish_queue=finish_queue)

    def client_console(self, text):
        self._conn.root.console(text)


class ClientService(rpyc.Service):
    def on_connect(self):
        """Make sure the client version matches our own."""
        daemon_version = self._conn.root.version()
        if IPC_VERSION != daemon_version:
            self._conn.close()
            raise ValueError('Daemon is different version than client.')

    def exposed_version(self):
        return IPC_VERSION

    def exposed_console(self, text):
        console(text)


class IPCServer(threading.Thread):
    def __init__(self, manager, port=None):
        super(IPCServer, self).__init__(name='ipc_server')
        self.daemon = True
        self.manager = manager
        self.host = '127.0.0.1'
        self.port = port or 0
        self.password = ''.join(random.choice(string.letters + string.digits) for x in range(15))
        self.server = None

    def authenticator(self, sock):
        channel = rpyc.Channel(rpyc.SocketStream(sock))
        password = channel.recv()
        if password != self.password:
            channel.send(AUTH_ERROR)
            raise rpyc.utils.authenticators.AuthenticationError('Invalid password from client.')
        channel.send(AUTH_SUCCESS)
        return sock, self.password

    def run(self):
        DaemonService.manager = self.manager
        self.server = ThreadedServer(
            DaemonService, hostname=self.host, port=self.port, authenticator=self.authenticator, logger=log
        )
        # If we just chose an open port, write save the chosen one
        self.port = self.server.listener.getsockname()[1]
        self.manager.write_lock(ipc_info={'port': self.port, 'password': self.password})
        self.server.start()

    def shutdown(self):
        self.server.close()


class IPCClient(object):
    def __init__(self, port, password):
        channel = rpyc.Channel(rpyc.SocketStream.connect('127.0.0.1', port))
        channel.send(password)
        response = channel.recv()
        if response == AUTH_ERROR:
            # TODO: What to raise here. I guess we create a custom error
            raise ValueError('Invalid password for daemon')
        self.conn = rpyc.utils.factory.connect_channel(channel, service=ClientService)

    def close(self):
        self.conn.close()

    def __getattr__(self, item):
        """Proxy all other calls to the exposed daemon service."""
        return getattr(self.conn.root, item)
