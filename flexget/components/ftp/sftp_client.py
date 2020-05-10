import logging
import os
import posixpath
import time
from functools import partial
from urllib.parse import quote, urljoin

from flexget import plugin
from flexget.entry import Entry

# retry configuration constants
CONNECT_TRIES = 3
RETRY_INTERVAL = 15
RETRY_STEP = 5
SOCKET_TIMEOUT = 15

try:
    import pysftp
    logging.getLogger("paramiko").setLevel(logging.ERROR)
except ImportError:
    pysftp = None

local_path = os.path
remote_path = posixpath  # pysftp uses POSIX style paths


class SftpClient:
    def __init__(self, logger, host, port, username, password=None, private_key=None, private_key_pass=None):

        if not pysftp:
            raise plugin.DependencyError(
                issued_by='sftp_client',
                missing='pysftp',
                message='sftp client requires the pysftp Python module.',
            )

        self._logger = logger
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.private_key_pass = private_key_pass

        self.prefix = self._get_prefix()
        self._sftp = self._connect()
        self._handler_builder = HandlerBuilder(self._sftp, self._logger, self.prefix)

    def list_directories(self, directories, recursive, get_size, files_only):

        entries = []

        dir_handler = self._handler_builder.get_dir_handler(get_size, files_only, entries)
        file_handler = self._handler_builder.get_file_handler(get_size, entries)
        unknown_handler = self._handler_builder.get_unknown_handler()

        for directory in directories:
            try:
                self._sftp.walktree(directory, file_handler, dir_handler, unknown_handler, recursive)
            except IOError as e:
                self._logger.error('Failed to open {} ({})', directory, e)
                continue

        return entries

    def download(self, path, to, recursive, delete_origin):
        """
        Downloads the specified path
        """

        dir_handler = self._handler_builder.get_null_handler()
        unknown_handler = self._handler_builder.get_unknown_handler()

        if not self.path_exists(path):
            raise SftpError('Remote path does not exist: {}', path)

        if self.is_file(path):
            source_file = remote_path.basename(path)
            source_dir = remote_path.dirname(path)
            try:
                self._sftp.cwd(source_dir)
                self._download_file(source_file, to, delete_origin)
            except Exception as e:
                raise SftpError('Failed to download file %s (%s)' % (path, e))
        elif self.is_dir(path):
            base_path = remote_path.normpath(remote_path.join(path, '..'))
            dir_name = remote_path.basename(path)
            handle_file = partial(self._download_file, to, delete_origin)

            try:
                self._sftp.cwd(base_path)
                self._sftp.walktree(dir_name, handle_file, dir_handler, unknown_handler, recursive)
            except Exception as e:
                raise SftpError('Failed to download directory %s (%s)' % (path, e))

            if delete_origin:
                self.remove_dir(path)
        else:
            self._logger.warning('Skipping unknown file {}', path)

    def upload_file(self, source, to):

        filename = local_path.basename(source)
        destination = remote_path.join(to, filename)
        destination_url = urljoin(self.prefix, destination)

        if not os.path.exists(source):
            self._logger.warning('File no longer exists: {}', source)

        if not self.path_exists(to):
            try:
                self.make_dirs(to)
            except Exception as e:
                raise SftpError('Failed to create remote directory {} ({})', to, e)

        if not self.is_dir(to):
            raise SftpError('Not a directory: {}', to)

        try:
            self._put_file(source, destination)
            self._logger.verbose('Successfully uploaded {} to {}', source, destination_url)
        except IOError:
            raise SftpError('Remote directory does not exist: {} ({})', to)
        except Exception as e:
            raise SftpError('Failed to upload {} ({})', source, e)

    def remove_dir(self, path):
        """
        Remove a directory if it's empty
        """
        if self._sftp.exists(path) and not self._sftp.listdir(path):
            self._logger.debug('Attempting to delete directory {}', path)
            try:
                self._sftp.rmdir(path)
            except Exception as e:
                self._logger.error('Failed to delete directory {} ({})', path, e)

    def remove_file(self, path):
        self._logger.debug('Deleting remote file {}', path)
        try:
            self._sftp.remove(path)
        except Exception as e:
            self._logger.error('Failed to delete file {} ({})', path, e)
            return

    def is_file(self, path):
        return self._sftp.isfile(path)

    def is_dir(self, path):
        return self._sftp.isdir(path)

    def path_exists(self, path):
        """
        Check of a path exists

        :param path: Path to check
        :return: boolean indicating if the path exists
        """
        return self._sftp.lexists(path)

    def make_dirs(self, path):
        """
        Build directories

        :param path: path to build
        """
        self._sftp.makedirs(path)

    def _connect(self):
        """
        Connect to an sftp server
        """

        tries = CONNECT_TRIES
        retry_interval = RETRY_INTERVAL

        self._logger.debug('Connecting to {}', self.host)

        sftp = None

        while not sftp:
            try:
                sftp = pysftp.Connection(
                    host=self.host,
                    username=self.username,
                    private_key=self.private_key,
                    password=self.password,
                    port=self.port,
                    private_key_pass=self.private_key_pass,
                )
                timeout = SOCKET_TIMEOUT
                sftp.timeout = timeout
                self._logger.verbose('Connected to {}', self.host)
            except Exception as e:
                if not tries:
                    raise e
                else:
                    self._logger.debug('Caught exception: {}', e)
                    self._logger.warning(
                        'Failed to connect to {}; waiting {} seconds before retrying.',
                        self.host,
                        retry_interval,
                    )
                    time.sleep(retry_interval)
                    tries -= 1
                    retry_interval += RETRY_STEP

        return sftp

    def close(self):
        """
        Close the sftp connection
        """
        self._sftp.close()

    def _put_file(self, source, destination):
        return self._sftp.put(source, destination)

    def _download_file(self, source, destination, delete_origin):

        dir_name = remote_path.dirname(source)
        destination_path = self._build_destination_path(source, destination)
        destination_dir = local_path.dirname(destination)

        if local_path.exists(destination_path):
            self._logger.verbose('Skipping {} because destination file {} already exists. ', source, destination)
            return

        if not local_path.exists(destination_dir):
            os.makedirs(destination_dir)

        self._logger.verbose('Downloading file {} to {}', source, destination)

        try:
            self._sftp.get(source, destination_path)
        except Exception as e:
            self._logger.error('Failed to download {} ({})', source, e)
            if local_path.exists(destination_path):
                self._logger.debug('Removing partially downloaded file {}', destination_path)
                os.remove(destination_path)
            raise e

        if delete_origin:
            self.remove_file(source)
            self.remove_dir(dir_name)

    def _get_prefix(self):
        """
        Generate SFTP URL prefix
        """

        def get_login_string():
            if self.username and self.password:
                return '%s:%s@' % (self.username, self.password)
            elif self.username:
                return '%s@' % self.username
            else:
                return ''

        def get_port_string():
            if self.port and self.port != 22:
                return ':%d' % self.port
            else:
                return ''

        return 'sftp://%s%s%s/' % (get_login_string(), self.host, get_port_string())

    @classmethod
    def _build_destination_path(cls, path, destination):
        relative_path = local_path.join(*remote_path.split(path))  # convert remote path style to local style
        return local_path.join(destination, relative_path)


class SftpError(Exception):
    pass


class HandlerBuilder:
    """
    Class for building pysftp.Connection.walktree node handlers.

    :param sftp: A Connection object
    :param logger: a logger object
    :param url_prefix: SFTP URL prefix
    """

    def __init__(self, sftp, logger, url_prefix):
        self._sftp = sftp
        self._logger = logger
        self._prefix = url_prefix

    def get_file_handler(self, get_size, entry_accumulator):
        """
        Builds a file node handler suitable for use with pysftp.Connection.walktree

        :param get_size: boolean indicating whether to compute the for each file
        :param entry_accumulator: list to add entries to
        """
        return partial(Handlers.handle_file, self._sftp, self._logger, self._prefix, get_size, entry_accumulator)

    def get_dir_handler(self, get_size, files_only, entry_accumulator):
        """
        Builds a file node handler suitable for use with pysftp.Connection.walktree

        :param get_size: boolean indicating whether to compute the for each file
        :param files_only: Boolean indicating whether to skip directories
        :param entry_accumulator: list to add entries to
        """
        return partial(Handlers.handle_directory, self._sftp, self._logger, self._prefix, get_size, files_only,
                       entry_accumulator)

    def get_unknown_handler(self):
        """
        Builds an unknown node handler suitable for use with pysftp.Connection.walktree
        """
        return partial(Handlers.handle_unknown, self._logger)

    def get_null_handler(self):
        """
        Builds a noop node handler suitable for use with pysftp.Connection.walktree
        """
        return partial(Handlers.null_node_handler, self._logger)


class Handlers:
    @classmethod
    def handle_file(cls, sftp, logger, prefix, get_size, entry_accumulator, path):
        """
        File node handler. Adds a file entry to entry_accumulator.

        :param sftp: A pysftp.Connection object
        :param logger: a logger object
        :param prefix: SFTP URL prefix
        :param get_size: boolean indicating whether to compute the size of each file
        :param entry_accumulator: a list in which to store entries
        :param path: path to handle
        """
        size_handler = partial(cls._file_size, sftp)
        entry = cls._get_entry(sftp, logger, prefix, size_handler, get_size, path)
        entry_accumulator.append(entry)

    @classmethod
    def handle_directory(cls, sftp, logger, prefix, get_size, files_only, entry_accumulator, path):
        """
        Directory node handler. Adds a directory entry to entry_accumulator.

        :param sftp: A pysftp.Connection object
        :param logger: a logger object
        :param prefix: SFTP URL prefix
        :param get_size: boolean indicating whether to compute the size of each directory
        :param files_only: Boolean indicating whether to skip directories
        :param entry_accumulator: a list in which to store entries
        :param path: path to handle
        """
        if files_only:
            return

        dir_size = partial(cls._dir_size, sftp)
        entry = cls._get_entry(sftp, logger, prefix, dir_size, get_size, path)
        entry_accumulator.append(entry)

    @staticmethod
    def handle_unknown(logger, path):
        """
        Handler for unknown nodes; logs a warning.

        :param logger: a logger object
        :param path: path to handle
        """
        logger.warning('Skipping unknown file: {}', path)

    @staticmethod
    def null_node_handler(logger, path):
        """
        Generic noop node handler

        :param logger: a logger object
        :param path: path to handle
        :return:
        """
        logger.debug('null handler called  for {}', path)

    @staticmethod
    def _get_entry(sftp, logger, prefix, size_handler, get_size, path):

        url = urljoin(prefix, quote(sftp.normalize(path)))
        title = remote_path.basename(path)

        entry = Entry(title, url)

        if get_size:
            try:
                size = size_handler(path)
            except Exception as e:
                logger.error('Failed to get size for {} ({})', path, e)
                size = -1
            entry['content_size'] = size

        return entry

    @classmethod
    def _dir_size(cls, sftp, path):
        sizes = []

        size_accumulator = partial(cls._accumulate_file_size, sftp, sizes)
        sftp.walktree(path, size_accumulator, size_accumulator, size_accumulator, True)

        return sum(sizes)

    @classmethod
    def _accumulate_file_size(cls, sftp, size_accumulator, path):
        size_accumulator.append(cls._file_size(sftp, path))

    @staticmethod
    def _file_size(sftp, path):
        """
        Helper function to get the size of a file node
        """
        return sftp.lstat(path).st_size
