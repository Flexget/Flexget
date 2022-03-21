import logging
import time
from functools import partial
from pathlib import Path, PurePath, PurePosixPath
from typing import Callable, List, Optional
from urllib.parse import quote, urljoin

from loguru import logger

from flexget import plugin
from flexget.entry import Entry

# retry configuration constants
RETRY_INTERVAL_SEC: int = 15
RETRY_STEP_SEC: int = 5

try:
    import pysftp

    logging.getLogger("paramiko").setLevel(logging.ERROR)
except ImportError:
    pysftp = None

NodeHandler = Callable[[str], None]

logger = logger.bind(name='sftp_client')


class SftpClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        private_key_pass: Optional[str] = None,
        connection_tries: int = 3,
    ):

        if not pysftp:
            raise plugin.DependencyError(
                issued_by='sftp_client',
                missing='pysftp',
                message='sftp client requires the pysftp Python module.',
            )

        self.host: str = host
        self.port: int = port
        self.username: str = username
        self.password: Optional[str] = password
        self.private_key: Optional[str] = private_key
        self.private_key_pass: Optional[str] = private_key_pass

        self.prefix: str = self._get_prefix()
        self._sftp: 'pysftp.Connection' = self._connect(connection_tries)
        self._handler_builder: HandlerBuilder = HandlerBuilder(
            self._sftp, self.prefix, self.private_key, self.private_key_pass
        )

    def list_directories(
        self,
        directories: List[str],
        recursive: bool,
        get_size: bool,
        files_only: bool,
        dirs_only: bool,
    ) -> List[Entry]:
        """
        Build a list of entries from a provided list of directories on an SFTP server
        :param directories: list of directories to generate entries for
        :param recursive: boolean indicating whether to list recursively
        :param get_size: boolean indicating whether to compute size for each node (potentially slow for directories)
        :param files_only: boolean indicating whether to exclude directories
        :param dirs_only: boolean indicating whether to exclude files
        :return: a list of entries describing the contents of the provided directories
        """

        entries: List[Entry] = []

        dir_handler: NodeHandler = self._handler_builder.get_dir_handler(
            get_size, files_only, entries
        )
        file_handler: NodeHandler = self._handler_builder.get_file_handler(
            get_size, dirs_only, entries
        )
        unknown_handler: NodeHandler = self._handler_builder.get_unknown_handler()

        for directory in directories:
            try:
                self._sftp.walktree(
                    directory, file_handler, dir_handler, unknown_handler, recursive
                )
            except OSError as e:
                logger.warning('Failed to open {} ({})', directory, str(e))
                continue

        return entries

    def download(self, source: str, to: str, recursive: bool, delete_origin: bool) -> None:
        """
        Downloads the file specified in "source" to the destination specified in "to"
        :param source: path of the resource to download
        :param to: path of the directory to download to
        :param recursive: indicates whether to download the contents of "source" recursively
        :param delete_origin: indicates whether to delete the source resource upon download
        """

        dir_handler: NodeHandler = self._handler_builder.get_null_handler()
        unknown_handler: NodeHandler = self._handler_builder.get_unknown_handler()

        parsed_path: PurePosixPath = PurePosixPath(source)

        if not self.path_exists(source):
            raise SftpError(f'Remote path does not exist: {source}')

        if self.is_file(source):
            source_file: str = parsed_path.name
            source_dir: str = parsed_path.parent.as_posix()
            try:
                self._sftp.cwd(source_dir)
                self._download_file(to, delete_origin, source_file)
            except Exception as e:
                raise SftpError(f'Failed to download file {source} ({str(e)})')

            if delete_origin:
                self.remove_dir(source_dir)
        elif self.is_dir(source):
            base_path: str = parsed_path.joinpath('..').as_posix()
            dir_name: str = parsed_path.name
            handle_file: NodeHandler = partial(self._download_file, to, delete_origin)

            try:
                self._sftp.cwd(base_path)
                self._sftp.walktree(dir_name, handle_file, dir_handler, unknown_handler, recursive)
            except Exception as e:
                raise SftpError(f'Failed to download directory {source} ({str(e)})')

            if delete_origin:
                self.remove_dir(source)
        else:
            logger.warning('Skipping unknown file: {}', source)

    def upload(self, source: str, to: str) -> None:
        """
        Upload files or directories to an SFTP server
        :param source: file or directory to upload
        :param to: destination
        """
        if Path(source).is_dir():
            logger.verbose('Skipping directory {}', source)  # type: ignore
        else:
            self._upload_file(source, to)

    def remove_dir(self, path: str) -> None:
        """
        Remove a directory if it's empty
        :param path: directory to remove
        """
        if self._sftp.exists(path) and not self._sftp.listdir(path):
            logger.debug('Attempting to delete directory {}', path)
            try:
                self._sftp.rmdir(path)
            except Exception as e:
                logger.error('Failed to delete directory {} ({})', path, str(e))

    def remove_file(self, path: str) -> None:
        """
        Remove a file if it's empty
        :param path: file to remove
        """
        logger.debug('Deleting remote file {}', path)
        try:
            self._sftp.remove(path)
        except Exception as e:
            logger.error('Failed to delete file {} ({})', path, str(e))
            return

    def is_file(self, path: str) -> bool:
        """
        Check if the node at a given path is a file
        :param path: path to check
        :return: boolean indicating if the path is a file
        """
        return self._sftp.isfile(path)

    def is_dir(self, path: str) -> bool:
        """
        Check if the node at a given path is a directory
        :param path: path to check
        :return: boolean indicating if the path is a directory
        """
        return self._sftp.isdir(path)

    def path_exists(self, path: str) -> bool:
        """
        Check of a path exists

        :param path: Path to check
        :return: boolean indicating if the path exists
        """
        return self._sftp.lexists(path)

    def make_dirs(self, path: str) -> None:
        """
        Build directories

        :param path: path to build
        """

        if not self.path_exists(path):
            try:
                self._sftp.makedirs(path)
            except Exception as e:
                raise SftpError(f'Failed to create remote directory {path} ({str(e)})')

    def close(self) -> None:
        """
        Close the sftp connection
        """
        self._sftp.close()

    def set_socket_timeout(self, socket_timeout_sec):
        """
        Sets the SFTP client socket timeout
        :param socket_timeout_sec: Socket timeout in seconds
        """
        self._sftp.timeout = socket_timeout_sec

    def _connect(self, connection_tries: int) -> 'pysftp.Connection':

        tries: int = connection_tries
        retry_interval: int = RETRY_INTERVAL_SEC

        logger.debug('Connecting to {}', self.host)

        sftp: Optional['pysftp.Connection'] = None

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
                logger.verbose('Connected to {}', self.host)  # type: ignore
            except Exception as e:
                tries -= 1
                if not tries:
                    raise e
                else:
                    logger.debug('Caught exception: {}', e)
                    logger.warning(
                        'Failed to connect to {}; waiting {} seconds before retrying.',
                        self.host,
                        retry_interval,
                    )
                    time.sleep(retry_interval)
                    retry_interval += RETRY_STEP_SEC

        return sftp

    def _upload_file(self, source: str, to: str) -> None:
        if not Path(source).exists():
            logger.warning('File no longer exists:', source)
            return

        destination = self._get_upload_path(source, to)
        destination_url: str = urljoin(self.prefix, destination)

        if not self.path_exists(to):
            try:
                self.make_dirs(to)
            except Exception as e:
                raise SftpError(f'Failed to create remote directory {to} ({str(e)})')

        if not self.is_dir(to):
            raise SftpError(f'Not a directory: {to}')

        try:
            self._put_file(source, destination)
            logger.verbose('Successfully uploaded {} to {}', source, destination_url)  # type: ignore
        except OSError:
            raise SftpError(f'Remote directory does not exist: {to}')
        except Exception as e:
            raise SftpError(f'Failed to upload {source} ({str(e)})')

    def _download_file(self, destination: str, delete_origin: bool, source: str) -> None:

        destination_path: str = self._get_download_path(source, destination)
        destination_dir: str = Path(destination_path).parent.as_posix()

        if Path(destination_path).exists():
            logger.verbose(  # type: ignore
                'Skipping {} because destination file {} already exists.', source, destination_path
            )
            return

        Path(destination_dir).mkdir(parents=True, exist_ok=True)

        logger.verbose('Downloading file {} to {}', source, destination)  # type: ignore

        try:
            self._sftp.get(source, destination_path)
        except Exception as e:
            logger.error('Failed to download {} ({})', source, e)
            if Path(destination_path).exists():
                logger.debug('Removing partially downloaded file {}', destination_path)
                Path(destination_path).unlink()
            raise e

        if delete_origin:
            self.remove_file(source)

    def _put_file(self, source: str, destination: str) -> None:
        return self._sftp.put(source, destination)

    def _get_prefix(self) -> str:
        """
        Generate SFTP URL prefix
        """

        def get_login_string() -> str:
            if self.username and self.password:
                return f'{self.username}:{self.password}@'
            elif self.username:
                return f'{self.username}@'
            else:
                return ''

        def get_port_string() -> str:
            if self.port and self.port != 22:
                return f':{self.port}'
            else:
                return ''

        login_string = get_login_string()
        host = self.host
        port_string = get_port_string()

        return f'sftp://{login_string}{host}{port_string}/'

    @staticmethod
    def _get_download_path(path: str, destination: str) -> str:
        return PurePosixPath(destination).joinpath(Path(path)).as_posix()

    @staticmethod
    def _get_upload_path(source: str, to: str):
        basename: str = PurePath(source).name
        return PurePosixPath(to, basename).as_posix()


class SftpError(Exception):
    pass


class HandlerBuilder:
    """
    Class for building pysftp.Connection.walktree node handlers.

    :param sftp: A Connection object
    :param logger: a logger object
    :param url_prefix: SFTP URL prefix
    """

    def __init__(
        self,
        sftp: 'pysftp.Connection',
        url_prefix: str,
        private_key: Optional[str],
        private_key_pass: Optional[str],
    ):
        self._sftp = sftp
        self._prefix = url_prefix
        self._private_key = private_key
        self._private_key_pass = private_key_pass

    def get_file_handler(
        self, get_size: bool, dirs_only: bool, entry_accumulator: list
    ) -> NodeHandler:
        """
        Builds a file node handler suitable for use with pysftp.Connection.walktree

        :param get_size: boolean indicating whether to compute the for each file
        :param dirs_only: boolean indicating whether to skip files
        :param entry_accumulator: list to add entries to
        """
        return partial(
            Handlers.handle_file,
            self._sftp,
            self._prefix,
            get_size,
            dirs_only,
            self._private_key,
            self._private_key_pass,
            entry_accumulator,
        )

    def get_dir_handler(
        self, get_size: bool, files_only: bool, entry_accumulator: list
    ) -> NodeHandler:
        """
        Builds a file node handler suitable for use with pysftp.Connection.walktree

        :param get_size: boolean indicating whether to compute the for each file
        :param files_only: Boolean indicating whether to skip directories
        :param entry_accumulator: list to add entries to
        """
        return partial(
            Handlers.handle_directory,
            self._sftp,
            self._prefix,
            get_size,
            files_only,
            self._private_key,
            self._private_key_pass,
            entry_accumulator,
        )

    def get_unknown_handler(self) -> NodeHandler:
        """
        Builds an unknown node handler suitable for use with pysftp.Connection.walktree
        """
        return partial(Handlers.handle_unknown)

    def get_null_handler(self) -> NodeHandler:
        """
        Builds a noop node handler suitable for use with pysftp.Connection.walktree
        """
        return partial(Handlers.null_node_handler)


class Handlers:
    @classmethod
    def handle_file(
        cls,
        sftp: 'pysftp.Connection',
        prefix: str,
        get_size: bool,
        dirs_only: bool,
        private_key: Optional[str],
        private_key_pass: Optional[str],
        entry_accumulator: List[Entry],
        path: str,
    ) -> None:
        """
        File node handler. Adds a file entry to entry_accumulator.

        :param sftp: A pysftp.Connection object
        :param logger: a logger object
        :param prefix: SFTP URL prefix
        :param get_size: boolean indicating whether to compute the size of each file
        :param dirs_only: boolean indicating whether to skip files
        :param private_key: private key path
        :param private_key_pass: private key password
        :param entry_accumulator: a list in which to store entries
        :param path: path to handle
        """
        if dirs_only:
            return

        size_handler = partial(cls._file_size, sftp)
        entry = cls._get_entry(
            sftp, prefix, size_handler, get_size, path, private_key, private_key_pass
        )
        entry_accumulator.append(entry)

    @classmethod
    def handle_directory(
        cls,
        sftp: 'pysftp.Connection',
        prefix: str,
        get_size: bool,
        files_only: bool,
        private_key: Optional[str],
        private_key_pass: Optional[str],
        entry_accumulator: List[Entry],
        path: str,
    ) -> None:
        """
        Directory node handler. Adds a directory entry to entry_accumulator.

        :param sftp: A pysftp.Connection object
        :param logger: a logger object
        :param prefix: SFTP URL prefix
        :param get_size: boolean indicating whether to compute the size of each directory
        :param files_only: Boolean indicating whether to skip directories
        :param entry_accumulator: a list in which to store entries
        :param private_key: private key path
        :param private_key_pass: private key password
        :param path: path to handle
        """
        if files_only:
            return

        dir_size: Callable[[str], int] = partial(cls._dir_size, sftp)
        entry: Entry = cls._get_entry(
            sftp, prefix, dir_size, get_size, path, private_key, private_key_pass
        )
        entry_accumulator.append(entry)

    @staticmethod
    def handle_unknown(path: str) -> None:
        """
        Handler for unknown nodes; logs a warning.

        :param logger: a logger object
        :param path: path to handle
        """
        logger.warning('Skipping unknown file: {}', path)

    @staticmethod
    def null_node_handler(path: str) -> None:
        """
        Generic noop node handler

        :param logger: a logger object
        :param path: path to handle
        :return:
        """
        logger.debug('null handler called  for {}', path)

    @staticmethod
    def _get_entry(
        sftp: 'pysftp.Connection',
        prefix: str,
        size_handler: Callable[[str], int],
        get_size,
        path: str,
        private_key: Optional[str],
        private_key_pass: Optional[str],
    ) -> Entry:

        url = urljoin(prefix, quote(sftp.normalize(path)))
        title = PurePosixPath(path).name

        entry = Entry(title, url)

        if get_size:
            try:
                size = size_handler(path)
            except Exception as e:
                logger.warning('Failed to get size for {} ({})', path, e)
                size = -1
            entry['content_size'] = size

        entry['private_key'] = private_key
        entry['private_key_pass'] = private_key_pass

        return entry

    @classmethod
    def _dir_size(cls, sftp: 'pysftp.Connection', path: str) -> int:
        sizes: List[int] = []

        size_accumulator = partial(cls._accumulate_file_size, sftp, sizes)
        sftp.walktree(path, size_accumulator, size_accumulator, size_accumulator, True)

        return sum(sizes)

    @classmethod
    def _accumulate_file_size(
        cls, sftp: 'pysftp.Connection', size_accumulator: List[int], path: str
    ) -> None:
        size_accumulator.append(cls._file_size(sftp, path))

    @staticmethod
    def _file_size(sftp: 'pysftp.Connection', path: str) -> int:
        """
        Helper function to get the size of a file node
        """
        return sftp.lstat(path).st_size
