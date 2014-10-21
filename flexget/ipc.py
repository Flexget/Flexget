from __future__ import absolute_import, division, unicode_literals

import logging
import random
import string
import threading
import time

import rpyc
from rpyc.utils.server import ThreadedServer

from flexget.utils.log import capture_output
from flexget.utils.tools import console

log = logging.getLogger('ipc')

# Allow some attributes from dict interface to be called over the wire
rpyc.core.protocol.DEFAULT_CONFIG['safe_attrs'].update(['items'])
rpyc.core.protocol.DEFAULT_CONFIG['allow_pickle'] = True

IPC_VERSION = 2
AUTH_ERROR = 'authentication error'
AUTH_SUCCESS = 'authentication success'


class RemoteStream(object):
    """
    Used as a filelike to stream text to remote client. If client disconnects while this is in use, an error will be
    logged, but no exception raised.
    """
    def __init__(self, writer):
        """
        :param writer: A function which writes a line of text to remote client.
        """
        self.writer = writer

    def write(self, data):
        if not self.writer:
            return
        try:
            self.writer(data.rstrip('\n'))
        except EOFError:
            self.writer = None
            log.error('Client ended connection while still streaming output.')


class DaemonService(rpyc.Service):
    # This will be populated when the server is started
    manager = None

    def exposed_version(self):
        return IPC_VERSION

    def exposed_execute(self, options=None):
        with capture_output(self.client_out_stream):
            if options:
                # Dictionaries are pass by reference with rpyc, turn this into a real dict on our side
                options = rpyc.utils.classic.obtain(options)
            log.info('Adding execution for client.')
            if len(self.manager.task_queue) > 0:
                log.info('There is already an execution running. This one will execute next.')
            cron = options and options.get('cron')
            output = None if cron else self.client_out_stream
            tasks_finished = self.manager.execute(options=options, output=output)
        if output:
            # The task logs are being streamed back to client, wait until they have finished
            while any(not t.is_set() for t in tasks_finished):
                time.sleep(0.3)

    def exposed_reload(self):
        with capture_output(self.client_out_stream):
            log.info('Reloading config from disk.')
            try:
                self.manager.load_config()
            except ValueError as e:
                log.error('Error loading config: %s' % e.args[0])
            else:
                log.info('Config successfully reloaded from disk.')

    def exposed_shutdown(self, finish_queue=False):
        with capture_output(self.client_out_stream):
            log.info('Shutdown requested over ipc.')
            self.manager.shutdown(finish_queue=finish_queue)

    def client_console(self, text):
        self._conn.root.console(text)

    @property
    def client_out_stream(self):
        return RemoteStream(self._conn.root.console)


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
