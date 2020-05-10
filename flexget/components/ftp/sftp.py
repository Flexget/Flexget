import os
from collections import namedtuple
from itertools import groupby
from urllib.parse import unquote, urlparse

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.template import RenderError, render_from_entry
from flexget.components.ftp.sftp_client import SftpClient, SftpError

logger = logger.bind(name='sftp')


SftpConfig = namedtuple(
    'SftpConfig', ['host', 'port', 'username', 'password', 'private_key', 'private_key_pass']
)


class SftpList:
    """
    Generate entries from SFTP. This plugin requires the pysftp Python module and its dependencies.

    Configuration:

    host:                 Host to connect to
    port:                 Port the remote SSH server is listening on. Defaults to port 22.
    username:             Username to log in as
    password:             The password to use. Optional if a private key is provided.
    private_key:          Path to the private key (if any) to log into the SSH server
    private_key_pass:     Password for the private key (if needed)
    recursive:            Indicates whether the listing should be recursive
    get_size:             Indicates whetern to calculate the size of the remote file/directory.
                          WARNING: This can be very slow when computing the size of directories!
    files_only:           Indicates wheter to omit diredtories from the results.
    dirs:                 List of directories to download

    Example:

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
            'port': {'type': 'integer', 'default': 22},
            'files_only': {'type': 'boolean', 'default': True},
            'recursive': {'type': 'boolean', 'default': False},
            'get_size': {'type': 'boolean', 'default': True},
            'private_key': {'type': 'string'},
            'private_key_pass': {'type': 'string'},
            'dirs': one_or_more({'type': 'string'}),
        },
        'additionProperties': False,
        'required': ['host', 'username'],
    }

    @classmethod
    def prepare_config(cls, config):
        """
        Sets defaults for the provided configuration
        """
        config.setdefault('port', 22)
        config.setdefault('password', None)
        config.setdefault('private_key', None)
        config.setdefault('private_key_pass', None)
        config.setdefault('dirs', ['.'])

        return config

    @classmethod
    def on_task_input(cls, task, config):
        """
        Input task handler
        """

        config = cls.prepare_config(config)

        files_only = config['files_only']
        recursive = config['recursive']
        get_size = config['get_size']

        directories = config['dirs']
        if not isinstance(directories, list):
            directories = [directories]

        sftp_config = task_config_to_sftp_config(config)
        sftp = sftp_connect(sftp_config)

        entries = sftp.list_directories(directories, recursive, get_size, files_only)
        sftp.close()

        return entries


class SftpDownload:
    """
    Download files from a SFTP server. This plugin requires the pysftp Python module and its
    dependencies.

    Configuration:

    to:                 Destination path; supports Jinja2 templating on the input entry. Fields such
                        as series_name must be populated prior to input into this plugin using
                        metainfo_series or similar.
    recursive:          Indicates wether to download directory contents recursively.
    delete_origin:      Indicates wether to delete the remote files(s) once they've been downloaded.

    Example:

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
        },
        'required': ['to'],
        'additionalProperties': False,
    }

    @classmethod
    def download_entry(cls, entry, config, sftp):
        """
        Downloads the file(s) described in entry
        """
        path = unquote(urlparse(entry['url']).path) or '.'
        delete_origin = config['delete_origin']
        recursive = config['recursive']
        to = config['to']

        try:
            sftp.download(path, to, recursive, delete_origin)
        except SftpError as e:
            logger.error(e)
            entry.fail(e)

    @classmethod
    def on_task_output(cls, task, config):
        """Register this as an output plugin"""

    @classmethod
    def on_task_download(cls, task, config):
        """
        Task handler for sftp_download plugin
        """

        # Download entries by host so we can reuse the connection
        for sftp_config, entries in groupby(task.accepted, cls._get_sftp_config):
            if not sftp_config:
                continue

            error_message = None
            sftp = None
            try:
                sftp = sftp_connect(sftp_config)
            except Exception as e:
                error_message = 'Failed to connect to %s (%s)' % (sftp_config.host, e)
                logger.error(error_message)

            for entry in entries:
                if sftp:
                    cls.download_entry(entry, config, sftp)
                else:
                    entry.fail(error_message)
            if sftp:
                sftp.close()

    @classmethod
    def _get_sftp_config(cls, entry):
        """
        Parses a url and returns a hashable config, source path, and destination path
        """
        # parse url
        parsed = urlparse(entry['url'])
        host = parsed.hostname
        username = parsed.username or None
        password = parsed.password or None
        port = parsed.port or 22

        # get private key info if it exists
        private_key = entry.get('private_key')
        private_key_pass = entry.get('private_key_pass')

        if parsed.scheme == 'sftp':
            config = SftpConfig(
                host, port, username, password, private_key, private_key_pass
            )
        else:
            logger.warning('Scheme does not match SFTP: {}', entry['url'])
            config = None

        return config


class SftpUpload:
    """
    Upload files to a SFTP server. This plugin requires the pysftp Python module and its
    dependencies.

    host:                 Host to connect to
    port:                 Port the remote SSH server is listening on. Defaults to port 22.
    username:             Username to log in as
    password:             The password to use. Optional if a private key is provided.
    private_key:          Path to the private key (if any) to log into the SSH server
    private_key_pass:     Password for the private key (if needed)
    to:                   Path to upload the file to; supports Jinja2 templating on the input entry. Fields such
                          as series_name must be populated prior to input into this plugin using
                          metainfo_series or similar.
    delete_origin:        Indicates wheter to delete the original file after a successful
                          upload.

    Example:

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
            'port': {'type': 'integer', 'default': 22},
            'private_key': {'type': 'string'},
            'private_key_pass': {'type': 'string'},
            'to': {'type': 'string'},
            'delete_origin': {'type': 'boolean', 'default': False},
        },
        'additionProperties': False,
        'required': ['host', 'username'],
    }

    @classmethod
    def prepare_config(cls, config):
        """
        Sets defaults for the provided configuration
        """
        config.setdefault('password', None)
        config.setdefault('private_key', None)
        config.setdefault('private_key_pass', None)
        config.setdefault('to', None)

        return config

    @classmethod
    def handle_entry(cls, entry, sftp, config):

        to = config['to']
        location = entry['location']

        if to:
            try:
                to = render_from_entry(to, entry)
            except RenderError as e:
                logger.error('Could not render path: {}', to)
                entry.fail(e)
                return

        try:
            sftp.upload_file(location, to)
        except SftpError as e:
            entry.fail(e)
            raise e

        if config['delete_origin']:
            try:
                os.remove(location)
            except Exception as e:
                logger.error('Failed to delete file {} ({})', location, e)

    @classmethod
    def on_task_output(cls, task, config):
        """Uploads accepted entries to the specified SFTP server."""

        config = cls.prepare_config(config)

        sftp_config = task_config_to_sftp_config(config)
        sftp = sftp_connect(sftp_config)

        for entry in task.accepted:
            if sftp:
                logger.debug('Uploading file: {}', entry['location'])
                cls.handle_entry(entry, sftp, config)
            else:
                logger.debug('SFTP connection failed; failing entry: {}', entry['title'])
                entry.fail('SFTP connection failed; failing entry: %s' % entry['title'])


def task_config_to_sftp_config(config):
    """
    Creates an SFTP connection from a Flexget config object
    """
    host = config['host']
    port = config['port']
    username = config['username']
    password = config['password']
    private_key = config['private_key']
    private_key_pass = config['private_key_pass']

    return SftpConfig(host, port, username, password, private_key, private_key_pass)


def sftp_connect(sftp_config):
    return SftpClient(
        logger=logger,
        host=sftp_config.host,
        username=sftp_config.username,
        private_key=sftp_config.private_key,
        password=sftp_config.password,
        port=sftp_config.port,
        private_key_pass=sftp_config.private_key_pass,
    )


@event('plugin.register')
def register_plugin():
    plugin.register(SftpList, 'sftp_list', api_ver=2)
    plugin.register(SftpDownload, 'sftp_download', api_ver=2)
    plugin.register(SftpUpload, 'sftp_upload', api_ver=2)
