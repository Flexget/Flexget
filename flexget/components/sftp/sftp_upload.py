from __future__ import annotations

import asyncio
import contextlib
import shutil
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from loguru import logger

from flexget import plugin
from flexget.components.sftp.base import (
    DEFAULT_CONNECT_TRIES,
    DEFAULT_SFTP_PORT,
    DEFAULT_SOCKET_TIMEOUT_SEC,
    SFTPConfig,
    SFTPManager,
)
from flexget.event import event
from flexget.utils.template import RenderError, render_from_entry

if TYPE_CHECKING:
    from loguru import Logger

    from flexget.entry import Entry
    from flexget.task import Task

with contextlib.suppress(ImportError):
    import asyncssh
    from asyncssh import ConnectionLost, SFTPConnectionLost

logger = logger.bind(name='sftp_upload')


class SFTPUpload:
    """Upload files to a SFTP server. This plugin requires the asyncssh Python module and its dependencies.

    ==================    ======================================================================================
    Option                Description
    ==================    ======================================================================================
    host                  Host to connect to
    port                  Port the remote SSH server is listening on. Defaults to port 22.
    username              Username to log in as
    password              The password to use. Optional if a private key is provided.
    private_key           Path to the private key (if any) to log into the SSH server
    private_key_pass      Password for the private key (if needed)
    to                    Path to upload the file to; supports Jinja2 templating on the input entry. Fields such
                          as series_name must be populated prior to input into this plugin using
                          metainfo_series or similar.
    delete_origin         Indicates whether to delete the original file after a successful
                          upload.
    socket_timeout_sec    Socket timeout in seconds
    connection_tries      Number of times to attempt to connect before failing (default 3).
    host_key              Specifies a host key not already in known_hosts
    ==================    ======================================================================================

    Example::

      sftp_list:
          host: example.com
          username: Username
          private_key: /Users/username/.ssh/id_rsa
          to: /TV/{{series_name}}/Series {{series_season}}
          delete_origin: False
    """

    schema = {
        'type': 'object',
        'properties': {
            'host': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'port': {'type': 'integer', 'default': DEFAULT_SFTP_PORT},
            'private_key': {'type': 'string'},
            'private_key_pass': {'type': 'string'},
            'to': {'type': 'string', 'default': '/'},
            'delete_origin': {'type': 'boolean', 'default': False},
            'host_key': {
                'type': 'object',
                'properties': {
                    'key_type': {'type': 'string'},
                    'public_key': {'type': 'string'},
                },
                'required': ['key_type', 'public_key'],
                'additionalProperties': False,
            },
            'socket_timeout_sec': {'type': 'integer', 'default': DEFAULT_SOCKET_TIMEOUT_SEC},
            'connection_tries': {'type': 'integer', 'default': DEFAULT_CONNECT_TRIES},
        },
        'additionalProperties': False,
        'required': ['host', 'username'],
    }

    @classmethod
    def on_task_output(cls, task: Task, config: dict) -> None:
        """Upload accepted entries to the specified SFTP server."""
        if task.accepted:
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
            sftp_manager = SFTPUploadManager(
                sftp_config=sftp_config,
                entries=task.accepted,
                to=config['to'],
                delete_origin=config['delete_origin'],
                connection_tries=config['connection_tries'],
                logger=logger,
                max_concurrent_entry_requests=3,
            )
            asyncio.run(sftp_manager.run())


class SFTPUploadManager(SFTPManager):
    def __init__(
        self,
        *,
        sftp_config: SFTPConfig,
        entries: list[Entry],
        to: str,
        delete_origin: bool,
        connection_tries: int,
        logger: Logger,
        max_concurrent_entry_requests: int,
    ):
        super().__init__(
            sftp_config=sftp_config,
            connection_tries=connection_tries,
            logger=logger,
        )
        self.queue = asyncio.Queue()
        for item in entries:
            self.queue.put_nowait(item)
        self.to = to
        self.delete_origin = delete_origin
        self.max_concurrent_entry_requests = max_concurrent_entry_requests

    async def run(self):
        await self.connect()
        await asyncio.gather(*[self.worker() for _ in range(self.max_concurrent_entry_requests)])
        await self.disconnect()

    async def worker(self):
        while not self.queue.empty():
            await self.ready.wait()
            try:
                entry = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if self.reconnect_failed:
                entry.fail('All connection attempts failed')
                break
            local_path = entry.get('location')
            if not local_path:
                logger.error(
                    'Entry {} does not have a "location" field, skipping.', entry['title']
                )
                entry.fail('Missing location field')
                continue
            logger.debug('Uploading file: {}', local_path)
            try:
                to = render_from_entry(self.to, entry)
            except RenderError as e:
                logger.error('Could not render path: {}', self.to)
                entry.fail(str(e))
                continue
            worker_version = self.connection_version
            sftp = self.sftp
            try:
                await sftp.makedirs(to, exist_ok=True)
                await sftp.put(
                    local_path,
                    PurePosixPath(to) / Path(local_path).name,
                    preserve=True,
                    recurse=True,
                    follow_symlinks=True,
                )
            except (ConnectionLost, SFTPConnectionLost):
                self.queue.put_nowait(entry)
                await self.connect(worker_version)
            except (OSError, asyncssh.Error) as e:
                entry.fail(str(e))
            else:
                if self.delete_origin:
                    delete(local_path)


def delete(path: str | Path) -> None:
    path = Path(path)
    if path.is_symlink():
        delete(path.resolve(strict=True))
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()


@event('plugin.register')
def register_plugin() -> None:
    plugin.register(SFTPUpload, 'sftp_upload', api_ver=2)
