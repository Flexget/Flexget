from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import unquote, urlparse

from loguru import logger

from flexget import plugin
from flexget.components.ftp.sftp_client import HOST_KEY_TYPES, HostKey, SftpClient, SftpError
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.template import RenderError, render_from_entry

if TYPE_CHECKING:
    from pathlib import Path

    from flexget.entry import Entry
    from flexget.task import Task

logger = logger.bind(name='sftp')

# Constants
DEFAULT_SFTP_PORT: int = 22
DEFAULT_CONNECT_TRIES: int = 3
DEFAULT_SOCKET_TIMEOUT_SEC: int = 15


class SftpConfig(NamedTuple):
    host: str
    port: int
    username: str
    password: str
    private_key: str
    private_key_pass: str
    host_key: HostKey


class SftpList:
    """Generate entries from SFTP. This plugin requires the pysftp Python module and its dependencies.

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
    files_only            Indicates wheter to omit diredtories from the results.
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
            'dirs': one_or_more({'type': 'string'}),
            'socket_timeout_sec': {'type': 'integer', 'default': DEFAULT_SOCKET_TIMEOUT_SEC},
            'connection_tries': {'type': 'integer', 'default': DEFAULT_CONNECT_TRIES},
            'host_key': {
                'type': 'object',
                'properties': {
                    'key_type': {'type': 'string', 'enum': list(HOST_KEY_TYPES.keys())},
                    'public_key': {'type': 'string'},
                },
                'required': ['key_type', 'public_key'],
                'additionalProperties': False,
            },
        },
        'additionalProperties': False,
        'required': ['host', 'username'],
    }

    @staticmethod
    def prepare_config(config: dict) -> dict:
        """Set defaults for the provided configuration."""
        config.setdefault('password', None)
        config.setdefault('private_key', None)
        config.setdefault('private_key_pass', None)
        config.setdefault('host_key', None)
        config.setdefault('dirs', ['.'])

        return config

    @classmethod
    def on_task_input(cls, task: Task, config: dict) -> list[Entry]:
        """Input task handler."""
        config = cls.prepare_config(config)

        files_only: bool = config['files_only']
        dirs_only: bool = config['dirs_only']
        recursive: bool = config['recursive']
        get_size: bool = config['get_size']
        socket_timeout_sec: int = config['socket_timeout_sec']
        connection_tries: int = config['connection_tries']
        directories: list[str] = []

        if files_only and dirs_only:
            logger.warning(
                'Both files_only and dirs_only are set.  This will result in no entries being discovered.'
            )

        if isinstance(config['dirs'], list):
            directories.extend(config['dirs'])
        else:
            directories.append(config['dirs'])

        sftp_config: SftpConfig = task_config_to_sftp_config(config)
        sftp: SftpClient = sftp_connect(sftp_config, socket_timeout_sec, connection_tries)

        entries: list[Entry] = sftp.list_directories(
            directories, recursive, get_size, files_only, dirs_only
        )
        sftp.close()

        return entries


class SftpDownload:
    """Download files from a SFTP server.

    This plugin requires the pysftp Python module and its dependencies.

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
    def download_entry(cls, entry: Entry, config: dict, sftp: SftpClient) -> None:
        """Download the file(s) described in entry."""
        path: str = unquote(urlparse(entry['url']).path) or '.'
        delete_origin: bool = config['delete_origin']
        recursive: bool = config['recursive']
        to: str = config['to']

        try:
            to = render_from_entry(to, entry)
        except RenderError as e:
            logger.error('Could not render path: {}', to)
            entry.fail(str(e))
            return

        try:
            sftp.download(path, to, recursive, delete_origin)
        except SftpError as e:
            entry.fail(e)

    @classmethod
    def on_task_output(cls, task: Task, config: dict) -> None:
        """Register this as an output plugin."""

    @classmethod
    def on_task_download(cls, task: Task, config: dict) -> None:
        """Task handler for sftp_download plugin."""
        socket_timeout_sec: int = config['socket_timeout_sec']
        connection_tries: int = config['connection_tries']

        # Download entries by host so we can reuse the connection
        for sftp_config, entries in groupby(task.accepted, cls._get_sftp_config):
            if not sftp_config:
                continue

            error_message: str | None = None
            sftp: SftpClient | None = None
            try:
                sftp = sftp_connect(sftp_config, socket_timeout_sec, connection_tries)
            except Exception as e:
                error_message = f'Failed to connect to {sftp_config.host} ({e})'

            for entry in entries:
                if sftp:
                    cls.download_entry(entry, config, sftp)
                else:
                    entry.fail(error_message)
            if sftp:
                sftp.close()

    @classmethod
    def _get_sftp_config(cls, entry: Entry):
        """Parse a url and return a hashable config, source path, and destination path."""
        # parse url
        parsed = urlparse(entry['url'])
        host: str = parsed.hostname
        username: str = parsed.username
        password: str = parsed.password
        port: int = parsed.port or DEFAULT_SFTP_PORT

        # get private key info if it exists
        private_key: str = entry.get('private_key')
        private_key_pass: str = entry.get('private_key_pass')

        entry_host_key_config: dict = entry.get('host_key')
        host_key: HostKey | None = None
        if entry_host_key_config:
            host_key = HostKey(
                entry_host_key_config['key_type'], entry_host_key_config['public_key']
            )

        config: SftpConfig | None = None

        if parsed.scheme == 'sftp':
            config = SftpConfig(
                host, port, username, password, private_key, private_key_pass, host_key
            )
        else:
            logger.warning('Scheme does not match SFTP: {}', entry['url'])

        return config


class SftpUpload:
    """Upload files to a SFTP server. This plugin requires the pysftp Python module and its dependencies.

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
            'to': {'type': 'string'},
            'delete_origin': {'type': 'boolean', 'default': False},
            'host_key': {
                'type': 'object',
                'properties': {
                    'key_type': {'type': 'string', 'enum': list(HOST_KEY_TYPES.keys())},
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

    @staticmethod
    def prepare_config(config: dict) -> dict:
        """Set defaults for the provided configuration."""
        config.setdefault('password', None)
        config.setdefault('private_key', None)
        config.setdefault('private_key_pass', None)
        config.setdefault('to', None)

        return config

    @classmethod
    def handle_entry(cls, entry: Entry, sftp: SftpClient, config: dict):
        to: str = config['to']
        location: Path = entry['location']
        delete_origin: bool = config['delete_origin']

        if to:
            try:
                to = render_from_entry(to, entry)
            except RenderError as e:
                logger.error('Could not render path: {}', to)
                entry.fail(str(e))
                return

        try:
            sftp.upload(location, to)
        except SftpError as e:
            entry.fail(str(e))
            return

        if delete_origin and location.is_file():
            try:
                location.unlink()
            except Exception as e:
                logger.warning('Failed to delete file {} ({})', location, e)

    @classmethod
    def on_task_output(cls, task: Task, config: dict) -> None:
        """Upload accepted entries to the specified SFTP server."""
        config = cls.prepare_config(config)

        socket_timeout_sec: int = config['socket_timeout_sec']
        connection_tries: int = config['connection_tries']

        sftp_config: SftpConfig = task_config_to_sftp_config(config)
        sftp = sftp_connect(sftp_config, socket_timeout_sec, connection_tries)

        for entry in task.accepted:
            if sftp:
                logger.debug('Uploading file: {}', entry['location'])
                cls.handle_entry(entry, sftp, config)
            else:
                entry.fail('SFTP connection failed.')


def task_config_to_sftp_config(config: dict) -> SftpConfig:
    """Create an SFTP connection from a Flexget config object."""
    host: int = config['host']
    port: int = config['port']
    username: str = config['username']
    password: str = config['password']
    private_key: str = config['private_key']
    private_key_pass: str = config['private_key_pass']

    host_key: HostKey | None = None
    if config.get('host_key') is not None:
        host_key = HostKey(config['host_key']['key_type'], config['host_key']['public_key'])

    return SftpConfig(host, port, username, password, private_key, private_key_pass, host_key)


def sftp_connect(
    sftp_config: SftpConfig, socket_timeout_sec: int, connection_tries: int
) -> SftpClient:
    sftp_client: SftpClient = SftpClient(
        host=sftp_config.host,
        username=sftp_config.username,
        private_key=sftp_config.private_key,
        password=sftp_config.password,
        port=sftp_config.port,
        private_key_pass=sftp_config.private_key_pass,
        host_key=sftp_config.host_key,
        connection_tries=connection_tries,
    )
    sftp_client.set_socket_timeout(socket_timeout_sec)

    return sftp_client


@event('plugin.register')
def register_plugin() -> None:
    plugin.register(SftpList, 'sftp_list', api_ver=2)
    plugin.register(SftpDownload, 'sftp_download', api_ver=2)
    plugin.register(SftpUpload, 'sftp_upload', api_ver=2)
