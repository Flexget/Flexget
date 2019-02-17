from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import random
import string
import sys
import threading

import rpyc
from rpyc.utils.server import ThreadedServer
from terminaltables.terminal_io import terminal_size

from flexget import terminal
from flexget.logger import capture_output
from flexget.terminal import console
from flexget.options import get_parser

log = logging.getLogger('ipc')

# Allow some attributes from dict interface to be called over the wire
rpyc.core.protocol.DEFAULT_CONFIG['safe_attrs'].update(['items'])
rpyc.core.protocol.DEFAULT_CONFIG['allow_pickle'] = True

IPC_VERSION = 4
AUTH_ERROR = b'authentication error'
AUTH_SUCCESS = b'authentication success'


class RemoteStream(object):
    """
    Used as a filelike to stream text to remote client. If client disconnects while this is in use, an error will be
    logged, but no exception raised.
    """

    def __init__(self, writer):
        """
        :param writer: A function which writes a line of text to remote client.
        """
        self.buffer = ''
        self.writer = writer

    def write(self, text):
        self.buffer += text
        if '\n' in self.buffer:
            self.flush()

    def flush(self):
        if self.buffer is None or self.writer is None:
            return
        try:
            self.writer(self.buffer, end='')
        except EOFError:
            self.writer = None
            log.error('Client ended connection while still streaming output.')
        finally:
            self.buffer = ''


class DaemonService(rpyc.Service):
    # This will be populated when the server is started
    manager = None

    def on_connect(self, conn):
        self._conn = conn
        super(DaemonService, self).on_connect(conn)

    def exposed_version(self):
        return IPC_VERSION

    def exposed_handle_cli(self, args):
        args = rpyc.utils.classic.obtain(args)
        log.verbose('Running command `%s` for client.' % ' '.join(args))
        parser = get_parser()
        try:
            options = parser.parse_args(args, file=self.client_out_stream)
        except SystemExit as e:
            if e.code:
                # TODO: Not sure how to properly propagate the exit code back to client
                log.debug('Parsing cli args caused system exit with status %s.' % e.code)
            return
        # Saving original terminal size to restore after monkeypatch
        original_terminal_info = terminal.terminal_info
        # Monkeypatching terminal_size so it'll work using IPC
        terminal.terminal_info = self._conn.root.terminal_info
        try:
            if not options.cron:
                with capture_output(self.client_out_stream, loglevel=options.loglevel):
                    self.manager.handle_cli(options)
            else:
                self.manager.handle_cli(options)
        finally:
            # Restoring original terminal_size value
            terminal.terminal_info = original_terminal_info

    def client_console(self, text):
        self._conn.root.console(text)

    @property
    def client_out_stream(self):
        return RemoteStream(self._conn.root.console)


class ClientService(rpyc.Service):
    def on_connect(self, conn):
        self._conn = conn
        """Make sure the client version matches our own."""
        daemon_version = self._conn.root.version()
        if IPC_VERSION != daemon_version:
            self._conn.close()
            raise ValueError('Daemon is different version than client.')
        super(ClientService, self).on_connect(conn)

    def exposed_version(self):
        return IPC_VERSION

    def exposed_console(self, text, *args, **kwargs):
        console(text, *args, **kwargs)

    def exposed_terminal_info(self):
        return {'size': terminal_size(), 'isatty': sys.stdout.isatty()}


class IPCServer(threading.Thread):
    def __init__(self, manager, port=None):
        super(IPCServer, self).__init__(name='ipc_server')
        self.daemon = True
        self.manager = manager
        self.host = '127.0.0.1'
        self.port = port or 0
        self.password = ''.join(
            random.choice(string.ascii_letters + string.digits) for x in range(15)
        )
        self.server = None

    def authenticator(self, sock):
        channel = rpyc.Channel(rpyc.SocketStream(sock))
        password = channel.recv().decode('utf-8')
        if password != self.password:
            channel.send(AUTH_ERROR)
            raise rpyc.utils.authenticators.AuthenticationError('Invalid password from client.')
        channel.send(AUTH_SUCCESS)
        return sock, self.password

    def run(self):
        # Make the rpyc logger a bit quieter when we aren't in debugging.
        rpyc_logger = logging.getLogger('ipc.rpyc')
        if logging.getLogger().getEffectiveLevel() > logging.DEBUG:
            rpyc_logger.setLevel(logging.WARNING)
        DaemonService.manager = self.manager
        self.server = ThreadedServer(
            DaemonService,
            hostname=self.host,
            port=self.port,
            authenticator=self.authenticator,
            logger=rpyc_logger,
        )
        # If we just chose an open port, write save the chosen one
        self.port = self.server.listener.getsockname()[1]
        self.manager.write_lock(ipc_info={'port': self.port, 'password': self.password})
        self.server.start()

    def shutdown(self):
        if self.server:
            self.server.close()


class IPCClient(object):
    def __init__(self, port, password):
        channel = rpyc.Channel(rpyc.SocketStream.connect('127.0.0.1', port))
        channel.send(password.encode('utf-8'))
        response = channel.recv()
        if response == AUTH_ERROR:
            # TODO: What to raise here. I guess we create a custom error
            raise ValueError('Invalid password for daemon')
        self.conn = rpyc.utils.factory.connect_channel(
            channel, service=ClientService, config={'sync_request_timeout': None}
        )

    def close(self):
        self.conn.close()

    def __getattr__(self, item):
        """Proxy all other calls to the exposed daemon service."""
        return getattr(self.conn.root, item)
