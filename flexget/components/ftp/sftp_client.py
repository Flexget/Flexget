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


# noinspection PyUnresolvedReferences
class SftpClient:
    def __init__(self, logger, host, port, username, password=None, private_key=None, private_key_pass=None):
        self._logger = logger
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.private_key_pass = private_key_pass

        self.prefix = self._get_prefix()
        self._sftp = None

        if pysftp:
            self.connect()
        else:
            raise plugin.DependencyError(
                issued_by='sftp_client',
                missing='pysftp',
                message='sftp client requires the pysftp Python module.',
            )

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
                self._logger.error('Failed to open {} ({})', dir, e)
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
        return self._sftp.lexists(path)

    def make_dirs(self, path):
        return self._sftp.makedirs(path)

    def connect(self):
        tries = CONNECT_TRIES
        retry_interval = RETRY_INTERVAL

        self._sftp = None

        self._logger.debug('Connecting to {}', self.host)

        while not self._sftp:
            try:
                self._sftp = pysftp.Connection(
                    host=self.host,
                    username=self.username,
                    private_key=self.private_key,
                    password=self.password,
                    port=self.port,
                    private_key_pass=self.private_key_pass,
                )
                timeout = SOCKET_TIMEOUT
                self._sftp.timeout = timeout
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

    def close(self):
        self._sftp.close()

    def _put_file(self, source, destination):
        return self._sftp.put(source, destination)

    def _download_file(self, source, destination, delete_origin):
        """
        Download a file from source to destination
        """

        dir_name = remote_path.dirname(source)

        destination = self._build_destination_path(source, destination)
        destination_dir = local_path.dirname(destination)

        if local_path.exists(destination):
            self._logger.verbose('Skipping {} because destination file {} already exists. ', source, destination)
            return

        if not local_path.exists(destination_dir):
            os.makedirs(destination_dir)

        self._logger.verbose('Downloading file {} to {}', source, destination)

        try:
            self._sftp.get(source, destination)
        except Exception as e:
            self._logger.error('Failed to download {} ({})', source, e)
            if local_path.exists(destination):
                self._logger.debug('Removing partially downloaded file {}', destination)
                os.remove(destination)
            raise e

        if delete_origin:
            self.remove_file(source)
            self.remove_dir(dir_name)

    def _get_prefix(self):
        """
        Generate SFTP URL prefix
        """
        login_str = ''
        port_str = ''

        if self.username and self.password:
            login_str = '%s:%s@' % (self.username, self.password)
        elif self.username:
            login_str = '%s@' % self.username

        if self.port and self.port != 22:
            port_str = ':%d' % self.port

        return 'sftp://%s%s%s/' % (login_str, self.host, port_str)

    @classmethod
    def _build_destination_path(cls, path, destination):
        relative_path = local_path.join(*remote_path.split(path))  # convert remote path style to local style
        return local_path.join(destination, relative_path)


class SftpError(Exception):
    pass


class HandlerBuilder:
    """
    Helper class for building PySftp single-argument node handlers.
    """
    def __init__(self, sftp, logger, url_prefix):
        self._sftp = sftp
        self._logger = logger
        self._prefix = url_prefix

    def get_file_handler(self, get_size, accumulator):
        return partial(Handlers.handle_file, self._sftp, self._logger, self._prefix, get_size, accumulator)

    def get_dir_handler(self, get_size, files_only, accumulator):
        return partial(Handlers.handle_directory, self._sftp, self._logger, self._prefix, get_size, files_only,
                       accumulator)

    def get_unknown_handler(self):
        return partial(Handlers.handle_unknown, self._logger)

    def get_null_handler(self):
        return partial(Handlers.null_node_handler, self._logger)


class Handlers:
    @classmethod
    def handle_file(cls, sftp, logger, prefix, get_size, accumulator, path):
        size_handler = partial(cls.file_size, sftp)
        entry = cls.get_entry(sftp, logger, prefix, size_handler, get_size, path)
        accumulator.append(entry)

    @classmethod
    def handle_directory(cls, sftp, logger, prefix, get_size, files_only, accumulator, path):
        if files_only:
            return

        dir_size = partial(cls.dir_size, sftp)
        entry = cls.get_entry(sftp, logger, prefix, dir_size, get_size, path)
        accumulator.append(entry)

    @staticmethod
    def get_entry(sftp, logger, prefix, size_handler, get_size, path):

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
    def dir_size(cls, sftp, path):
        sizes = []

        size_accumulator = partial(cls.accumulate_file_size, sftp, sizes)
        sftp.walktree(path, size_accumulator, size_accumulator, size_accumulator, True)

        return sum(sizes)

    @classmethod
    def accumulate_file_size(cls, sftp, accumulator, path):
        accumulator.append(cls.file_size(sftp, path))

    @staticmethod
    def file_size(sftp, path):
        """
        Helper function to get the size of a file node
        """
        return sftp.lstat(path).st_size

    @staticmethod
    def null_node_handler(logger, path):
        logger.trace('null handler called  for {}', path)

    @staticmethod
    def handle_unknown(logger, path):
        """
        Skip unknown files
        """
        logger.warning('Skipping unknown file: {}', path)
