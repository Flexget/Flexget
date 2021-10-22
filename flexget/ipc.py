import contextlib
import logging
import random
import string
import threading
import unittest.mock
from typing import Callable, Optional

import rpyc
from loguru import logger
from rpyc.utils.server import ThreadedServer

from flexget import terminal
from flexget.log import capture_logs
from flexget.options import get_parser

logger = logger.bind(name='ipc')

# Allow some attributes from dict interface to be called over the wire
rpyc.core.protocol.DEFAULT_CONFIG['safe_attrs'].update(['items'])
rpyc.core.protocol.DEFAULT_CONFIG['allow_pickle'] = True

IPC_VERSION = 4
AUTH_ERROR = b'authentication error'
AUTH_SUCCESS = b'authentication success'


class RemoteStream:
    """
    Used as a filelike to stream text to remote client. If client disconnects while this is in use, an error will be
    logged, but no exception raised.
    """

    def __init__(self, writer: Optional[Callable]):
        """
        :param writer: A function which writes a line of text to remote client.
        """
        self.buffer = ''
        self.writer = writer

    def write(self, text: str) -> None:
        self.buffer += text
        if '\n' in self.buffer:
            self.flush()

    def flush(self) -> None:
        if self.buffer is None or self.writer is None:
            return
        try:
            self.writer(self.buffer, end='')
        except EOFError:
            self.writer = None
            logger.error('Client ended connection while still streaming output.')
        finally:
            self.buffer = ''


class DaemonService(rpyc.Service):
    # This will be populated when the server is started
    manager = None

    def on_connect(self, conn):
        self._conn = conn
        super().on_connect(conn)

    def exposed_version(self):
        return IPC_VERSION

    def exposed_handle_cli(self, args):
        args = rpyc.utils.classic.obtain(args)
        logger.verbose('Running command `{}` for client.', ' '.join(args))
        parser = get_parser()
        try:
            options = parser.parse_args(args, file=self.client_out_stream)
        except SystemExit as e:
            if e.code:
                # TODO: Not sure how to properly propagate the exit code back to client
                logger.debug('Parsing cli args caused system exit with status {}.', e.code)
            return
        context_managers = []
        # Don't capture any output when used with --cron
        if not options.cron:
            # Monkeypatch the console function to be the one from the client
            # This means decisions about color formatting, and table sizes can be delayed and
            # decided based on the client terminal capabilities.
            context_managers.append(
                unittest.mock.patch('flexget.terminal._patchable_console', self._conn.root.console)
            )
            if options.loglevel != 'NONE':
                context_managers.append(capture_logs(self.client_log_sink, level=options.loglevel))
        with contextlib.ExitStack() as stack:
            for cm in context_managers:
                stack.enter_context(cm)
            self.manager.handle_cli(options)

    @property
    def client_out_stream(self):
        return RemoteStream(self._conn.root.console)

    def client_log_sink(self, message):
        return self._conn.root.log_sink(message)


class ClientService(rpyc.Service):
    def on_connect(self, conn):
        self._conn = conn
        """Make sure the client version matches our own."""
        daemon_version = self._conn.root.version()
        if IPC_VERSION != daemon_version:
            self._conn.close()
            raise ValueError('Daemon is different version than client.')
        super().on_connect(conn)

    def exposed_version(self):
        return IPC_VERSION

    def exposed_console(self, text, *args, **kwargs):
        text = rpyc.classic.obtain(text)
        terminal.console(text, *args, **kwargs)

    def exposed_log_sink(self, message):
        message = rpyc.classic.obtain(message)
        record = message.record
        level, message = record['level'].name, record['message']
        logger.patch(lambda r: r.update(record)).log(level, message)


class IPCServer:
    def __init__(self, manager, port=None):
        self.daemon = True
        self.manager = manager
        self.host = '127.0.0.1'
        self.port = port or 0
        self.password = ''.join(
            random.choice(string.ascii_letters + string.digits) for x in range(15)
        )
        self.server = None
        self._thread = None

    def start(self):
        if not self._thread:
            self._thread = threading.Thread(name='ipc_server', target=self.run)
        self._thread.start()

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
        if logger.level(self.manager.options.loglevel).no > logger.level('DEBUG').no:
            rpyc_logger.setLevel(logging.WARNING)
        DaemonService.manager = self.manager
        self.server = ThreadedServer(
            DaemonService,
            hostname=self.host,
            port=self.port,
            authenticator=self.authenticator,
            logger=rpyc_logger,
            # Timeout can happen when piping to 'less' and delaying scrolling to bottom. Make it a long timeout.
            protocol_config={'sync_request_timeout': 3600},
        )
        # If we just chose an open port, write save the chosen one
        self.port = self.server.listener.getsockname()[1]
        self.manager.write_lock(ipc_info={'port': self.port, 'password': self.password})
        self.server.start()

    def shutdown(self):
        if self.server:
            self.server.close()


class IPCClient:
    def __init__(self, port, password: str):
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
