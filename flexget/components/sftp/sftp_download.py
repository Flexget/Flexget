from __future__ import annotations

import asyncio
import contextlib
from itertools import groupby
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

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
    from anyio import Path
    from asyncssh import ConnectionLost, SFTPConnectionLost

logger = logger.bind(name='sftp_upload')


class SftpDownload:
    """Download files from a SFTP server.

    This plugin requires the asyncssh Python module and its dependencies.

    Configuration options

    ==================   =============================================================================
    Option               Description
    ==================   =============================================================================
    to                   Destination path; supports Jinja2 templating on the input entry. Fields such
                         as series_name must be populated prior to input into this plugin using
                         metainfo_series or similar.
    recursive            Indicates whether to download directory contents recursively.
    delete_origin        Indicates whether to delete the remote files(s) once they've been downloaded.
    socket_timeout_sec   Socket timeout in seconds
    connection_tries     Number of times to attempt to connect before failing (default 3).
    ==================   =============================================================================

    Example::

      sftp_download:
          to: '/Volumes/External/Drobo/downloads'
          delete_origin: False
    """

    schema = {
        'type': 'object',
        'properties': {
            'to': {'type': 'string', 'format': 'path'},
            'recursive': {'type': 'boolean', 'default': True},
            'delete_origin': {'type': 'boolean', 'default': False},
            'socket_timeout_sec': {'type': 'integer', 'default': DEFAULT_SOCKET_TIMEOUT_SEC},
            'connection_tries': {'type': 'integer', 'default': DEFAULT_CONNECT_TRIES},
        },
        'required': ['to'],
        'additionalProperties': False,
    }

    @classmethod
    def on_task_output(cls, task: Task, config: dict) -> None:
        """Register this as an output plugin."""

    @classmethod
    def on_task_download(cls, task: Task, config: dict) -> None:
        """Task handler for sftp_download plugin."""

        def _get_sftp_config(entry: Entry) -> SFTPConfig | None:
            """Parse a url and return a hashable config, source path, and destination path."""
            parse_result = urlparse(entry['url'])
            host_key: dict = entry.get('host_key')
            if parse_result.scheme != 'sftp':
                logger.warning('Scheme does not match SFTP: {}', entry['url'])
                return None
            return SFTPConfig(
                host=parse_result.hostname,
                port=parse_result.port or DEFAULT_SFTP_PORT,
                username=parse_result.username,
                password=parse_result.password,
                client_keys=entry.get('private_key'),
                passphrase=entry.get('private_key_pass'),
                login_timeout=config['socket_timeout_sec'],
                key_type=host_key['key_type'] if host_key else None,
                public_key=host_key['public_key'] if host_key else None,
            )

        # `groupby` requires the data to be pre-sorted on the grouping key.
        processed_items = [
            (sftp_config, entry)
            for entry in task.entries
            if (sftp_config := _get_sftp_config(entry))
        ]
        processed_items.sort(key=lambda x: x[0])
        sftp_managers = []
        # Download entries by `sftp_config` so we can reuse the connection
        for sftp_config, group_iterator in groupby(processed_items, lambda x: x[0]):
            entries = [item[1] for item in group_iterator]
            sftp_manager = SFTPDownloadManager(
                sftp_config=sftp_config,
                entries=entries,
                to=config['to'],
                recurse=config['recursive'],
                delete_origin=config['delete_origin'],
                connection_tries=config['connection_tries'],
                logger=logger,
                max_concurrent_entry_requests=3,
            )
            sftp_managers.append(sftp_manager)
        asyncio.run(run_all(sftp_managers, max_concurrent_connections=3))


async def run_all(
    sftp_managers: list[SFTPDownloadManager],
    max_concurrent_connections: int,
) -> None:
    await asyncio.gather(*[
        sftp_manager.run(asyncio.Semaphore(max_concurrent_connections))
        for sftp_manager in sftp_managers
    ])


class SFTPDownloadManager(SFTPManager):
    def __init__(
        self,
        *,
        sftp_config: SFTPConfig,
        entries: list[Entry],
        to: str,
        recurse: bool,
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
        self.recurse = recurse
        self.delete_origin = delete_origin
        self.max_concurrent_entry_requests = max_concurrent_entry_requests

    async def run(self, semaphore):
        async with semaphore:
            await self.connect()
            await asyncio.gather(*[
                self.worker() for _ in range(self.max_concurrent_entry_requests)
            ])
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
            logger.debug('Uploading file: {}', entry['url'])
            try:
                to = render_from_entry(self.to, entry)
            except RenderError as e:
                logger.error('Could not render path: {}', self.to)
                entry.fail(str(e))
                continue
            worker_version = self.connection_version
            sftp = self.sftp
            remote_path = unquote(urlparse(entry['url']).path)
            await Path(to).mkdir(parents=True, exist_ok=True)
            try:
                await sftp.get(
                    remote_path,
                    PurePosixPath(to) / Path(remote_path).name,
                    preserve=True,
                    recurse=self.recurse,
                    follow_symlinks=True,
                )
            except (ConnectionLost, SFTPConnectionLost):
                self.queue.put_nowait(entry)
                await self.connect(worker_version)
            except (OSError, asyncssh.Error) as e:
                entry.fail(str(e))
            else:
                if self.delete_origin:
                    try:
                        if await sftp.isdir(remote_path):
                            await sftp.rmtree(remote_path)
                        else:
                            await sftp.unlink(remote_path)
                    except (OSError, asyncssh.Error) as e:
                        logger.error('Failed to delete {}, reason: {}', remote_path, e)


@event('plugin.register')
def register_plugin() -> None:
    plugin.register(SftpDownload, 'sftp_download', api_ver=2)
