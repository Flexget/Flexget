from __future__ import annotations

import asyncio
import collections
import contextlib
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import quote, urljoin

from loguru import logger

from flexget import plugin
from flexget.components.sftp.base import (
    DEFAULT_CONNECT_TRIES,
    DEFAULT_SFTP_PORT,
    DEFAULT_SOCKET_TIMEOUT_SEC,
    SFTPConfig,
    SFTPManager,
)
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event

if TYPE_CHECKING:
    from loguru import Logger

    from flexget.task import Task

with contextlib.suppress(ImportError):
    import asyncssh
    from asyncssh import (
        FILEXFER_TYPE_DIRECTORY,
        FILEXFER_TYPE_SYMLINK,
        ConnectionLost,
        SFTPConnectionLost,
    )

logger = logger.bind(name='sftp_list')


class SftpList:
    """Generate entries from SFTP. This plugin requires the asyncssh Python module and its dependencies.

    Configuration options

    ==================    ========================================================================
    Option                Description
    ==================    ========================================================================
    host                  Host to connect to.
    port                  Port the remote SSH server is listening on (default 22).
    username              Username to log in as.
    password              The password to use. Optional if a private key is provided.
    private_key           Path to the private key (if any) to log into the SSH server.
    private_key_pass      Password for the private key (if needed).
    recursive             Indicates whether the listing should be recursive.
    get_size              Indicates whetern to calculate the size of the remote file/directory.
                          WARNING: This can be very slow when computing the size of directories!
    files_only            Indicates whether to omit diredtories from the results.
    dirs_only             Indicates whether to omit files from the results.
    dirs                  List of directories to download.
    socket_timeout_sec    Socket timeout in seconds (default 15 seconds).
    connection_tries      Number of times to attempt to connect before failing (default 3).
    host_key              Specifies a host key not already in known_hosts
    ==================    ========================================================================

    Example::

      sftp_list:
          host: example.com
          username: Username
          private_key: /Users/username/.ssh/id_rsa
          recursive: False
          get_size: True
          files_only: False
          dirs:
              - '/path/to/list/'
              - '/another/path/'
    """

    schema = {
        'type': 'object',
        'properties': {
            'host': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'port': {'type': 'integer', 'default': DEFAULT_SFTP_PORT},
            'files_only': {'type': 'boolean', 'default': True},
            'dirs_only': {'type': 'boolean', 'default': False},
            'recursive': {'type': 'boolean', 'default': False},
            'get_size': {'type': 'boolean', 'default': True},
            'private_key': {'type': 'string'},
            'private_key_pass': {'type': 'string'},
            'dirs': one_or_more({'type': 'string', 'default': '.'}),
            'socket_timeout_sec': {'type': 'integer', 'default': DEFAULT_SOCKET_TIMEOUT_SEC},
            'connection_tries': {'type': 'integer', 'default': DEFAULT_CONNECT_TRIES},
            'host_key': {
                'type': 'object',
                'properties': {
                    'key_type': {'type': 'string'},
                    'public_key': {'type': 'string'},
                },
                'required': ['key_type', 'public_key'],
                'additionalProperties': False,
            },
        },
        'additionalProperties': False,
        'required': ['host', 'username'],
    }

    @classmethod
    def on_task_input(cls, task: Task, config: dict) -> list[Entry]:
        """Input task handler."""
        host_key = config.get('host_key')
        sftp_config = SFTPConfig(
            host=config['host'],
            port=config['port'],
            username=config['username'],
            password=config.get('password'),
            client_keys=config.get('private_key'),
            passphrase=config.get('private_key_pass'),
            key_type=host_key['key_type'] if host_key else None,
            public_key=host_key['public_key'] if host_key else None,
            login_timeout=config['socket_timeout_sec'],
        )
        dirs = config['dirs']
        if isinstance(dirs, str):
            dirs = [dirs]
        if config['files_only'] and config['dirs_only']:
            logger.warning(
                'Both files_only and dirs_only are set. This will result in no entries being discovered.'
            )
        sftp_manager = SFTPListManager(
            sftp_config=sftp_config,
            files_only=config['files_only'],
            dirs_only=config['dirs_only'],
            recurse=config['recursive'],
            get_size=config['get_size'],
            connection_tries=config['connection_tries'],
            logger=logger,
            max_concurrent_requests=256,
        )
        return asyncio.run(sftp_manager.run([PurePosixPath(d) for d in dirs]))


class SFTPListManager(SFTPManager):
    def __init__(
        self,
        *,
        sftp_config: SFTPConfig,
        files_only: bool,
        dirs_only: bool,
        recurse: bool,
        get_size: bool,
        connection_tries: int,
        logger: Logger,
        max_concurrent_requests: int,
    ):
        super().__init__(
            sftp_config=sftp_config,
            connection_tries=connection_tries,
            logger=logger,
        )
        self.files_only = files_only
        self.dirs_only = dirs_only
        self.recurse = recurse
        self.get_size = get_size
        self.entries = []
        self.cwd = PurePosixPath('/')
        self.max_concurrent_requests = max_concurrent_requests
        self.queue: asyncio.Queue[PurePosixPath] = asyncio.Queue()
        self.url_prefix = f'sftp://{sftp_config.username}{f":{sftp_config.password}" if sftp_config.password else ""}@{sftp_config.host}:{sftp_config.port}'
        self.walked_dirs: set[PurePosixPath] = set()
        self.dir_sizes: dict[PurePosixPath, int] = collections.defaultdict(int)

    async def run(self, dirs: list[PurePosixPath]) -> list[Entry]:
        await self.connect()
        if any(not d.is_absolute() for d in dirs):
            await self.getcwd()
        for d in dirs:
            self.queue.put_nowait(d if d.is_absolute() else self.cwd / d)
        tasks = [asyncio.create_task(self._worker()) for _ in range(self.max_concurrent_requests)]
        await self.queue.join()
        for t in tasks:
            t.cancel()
        if self.recurse and not self.files_only:
            if self.get_size:
                # Sort directories by path depth in descending order for bottom-up accumulation
                sorted_dirs = sorted(self.walked_dirs, key=lambda p: len(p.parts), reverse=True)
                for d in sorted_dirs:
                    # Bubble up the directory's size to its parent if its parent was also scanned
                    if d.parent in self.walked_dirs:
                        self.dir_sizes[d.parent] += self.dir_sizes[d]
            for d in self.walked_dirs:
                self.add_entry(d, self.dir_sizes[d] if self.get_size else None)
        await self.disconnect()
        return self.entries

    async def _worker(self) -> None:
        while True:
            await self._process_dir(await self.queue.get())
            self.queue.task_done()

    async def _process_dir(self, directory: PurePosixPath) -> None:
        while True:
            await self.ready.wait()
            if self.reconnect_failed:
                break
            worker_version = self.connection_version
            sftp = self.sftp
            try:
                async for item in sftp.scandir(directory):
                    if item.filename in {'.', '..'}:
                        continue
                    full_path = directory / item.filename
                    item_type = item.attrs.type
                    item_size = item.attrs.size or 0
                    if item_type == FILEXFER_TYPE_SYMLINK:
                        realpath_attrs = await sftp.stat(full_path, follow_symlinks=True)
                        if realpath_attrs.type == FILEXFER_TYPE_DIRECTORY:
                            item_type = FILEXFER_TYPE_DIRECTORY
                        else:
                            item_size = realpath_attrs.size
                    if item_type == FILEXFER_TYPE_DIRECTORY:
                        if self.recurse:
                            self.queue.put_nowait(full_path)
                            self.walked_dirs.add(full_path)
                        elif not self.files_only:
                            self.add_entry(full_path, 0 if self.get_size else None)
                    else:
                        if not self.dirs_only:
                            self.add_entry(full_path, item_size if self.get_size else None)
                        if self.get_size:
                            self.dir_sizes[directory] += item_size
                break
            except (ConnectionLost, SFTPConnectionLost):
                await self.connect(worker_version)
            except (OSError, asyncssh.Error) as e:
                logger.error('Failed to generate entries in {}, reason: {}', directory, e)
                break

    def add_entry(self, path: PurePosixPath, size: int | None) -> None:
        if not path.is_absolute():
            path = self.cwd / path
        entry = Entry(title=path.name, url=urljoin(self.url_prefix, quote(str(path))))
        if self.sftp_config.client_keys:
            entry['private_key'] = self.sftp_config.client_keys
            if self.sftp_config.passphrase:
                entry['private_key_pass'] = self.sftp_config.passphrase
        if self.sftp_config.key_type and self.sftp_config.public_key:
            entry['host_key'] = {
                'key_type': self.sftp_config.key_type,
                'public_key': self.sftp_config.public_key,
            }
        if self.get_size:
            entry['content_size'] = size
        self.entries.append(entry)

    async def getcwd(self) -> None:
        while True:
            if self.reconnect_failed:
                break
            worker_version = self.connection_version
            try:
                self.cwd = PurePosixPath(await self.sftp.getcwd())
                break
            except (ConnectionLost, SFTPConnectionLost):
                await self.connect(worker_version)


@event('plugin.register')
def register_plugin() -> None:
    plugin.register(SftpList, 'sftp_list', api_ver=2)
