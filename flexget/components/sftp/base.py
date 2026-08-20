from __future__ import annotations

import asyncio
import contextlib
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from flexget.task import TaskAbort

if TYPE_CHECKING:
    from asyncssh import SFTPClient, SSHClientConnection
    from loguru import Logger

with contextlib.suppress(ImportError):
    import asyncssh
    from asyncssh import ConnectionLost, PermissionDenied, SFTPConnectionLost

DEFAULT_SFTP_PORT: int = 22
DEFAULT_CONNECT_TRIES: int = 3
DEFAULT_SOCKET_TIMEOUT_SEC: int = 120


@dataclass(frozen=True, order=True)
class SFTPConfig:
    host: str
    port: int
    username: str
    password: str | None
    client_keys: str | None
    passphrase: str | None
    login_timeout: float | int | str | None
    key_type: str | None
    public_key: str | None

    def build_connect_kwargs(self):
        kwargs = {k: v for k, v in asdict(self).items() if k not in ['key_type', 'public_key']}
        kwargs['known_hosts'] = (
            f'[{self.host}]:{self.port} {self.key_type} {self.public_key}'.encode()
            if self.key_type and self.public_key
            else None
        )
        return kwargs


class SFTPManager(ABC):
    @abstractmethod
    def __init__(
        self,
        *,
        sftp_config: SFTPConfig,
        connection_tries: int,
        logger: Logger,
    ):
        self.sftp_config = sftp_config
        self.connection_tries = connection_tries
        self.logger = logger
        self.sftp: SFTPClient | None = None
        self.conn: SSHClientConnection | None = None
        self.connection_version = 0
        self.lock = asyncio.Lock()  # Ensure only one worker is reconnecting
        self.ready = asyncio.Event()  # Ensure no connection is used while reconnecting
        self.reconnect_failed = False

    async def disconnect(self):
        if self.sftp:
            self.sftp.exit()
            await self.sftp.wait_closed()
        if self.conn:
            self.conn.close()
            await self.conn.wait_closed()

    async def connect(self, last_version: int = 0):
        """Ensure the connection is available.

        If the version is outdated, it indicates another worker is already reconnecting; in this case, simply wait.
        """
        async with self.lock:
            # Double-checked locking: A version update implies the reconnection process has already concluded.
            if self.connection_version > last_version:
                return
            self.logger.debug('Connecting (connection version v{})', self.connection_version + 1)
            self.ready.clear()  # Clear the event to pause all workers.
            await self.disconnect()
            retry_count = 0
            # Establish connection with exponential backoff retries
            while retry_count < self.connection_tries:
                try:
                    self.conn = await asyncssh.connect(**self.sftp_config.build_connect_kwargs())
                    self.sftp = await self.conn.start_sftp_client()
                    self.connection_version += 1
                    self.logger.debug(
                        'Successfully connected; current version: V{}',
                        self.connection_version,
                    )
                    break
                except PermissionDenied as e:
                    raise TaskAbort(str(e)) from e
                except (ConnectionLost, SFTPConnectionLost) as e:
                    retry_count += 1
                    wait = min(2**retry_count, 10)
                    self.logger.debug('Reconnection failed: {}. Retrying in {}s...', e, wait)
                    await asyncio.sleep(wait)
            else:
                self.reconnect_failed = True
                self.logger.error('All connection attempts failed. Aborting...')
            self.ready.set()  # Resume all workers
