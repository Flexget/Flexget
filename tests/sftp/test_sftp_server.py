from __future__ import annotations

import contextlib
import logging
import os
import posixpath
import socket
import threading
import time
from logging import Logger
from pathlib import Path, PurePosixPath

try:
    from paramiko import (
        RSAKey,
        ServerInterface,
        SFTPAttributes,
        SFTPHandle,
        SFTPServer,
        SFTPServerInterface,
        Transport,
    )
    from paramiko.common import AUTH_FAILED, AUTH_SUCCESSFUL, OPEN_SUCCEEDED
    from paramiko.sftp import SFTP_OK, SFTP_OP_UNSUPPORTED
except ImportError:
    pass
else:
    logger = logging.getLogger("StubSFTP")

    ADDRESS = '127.0.0.1'
    PORT = 40022

    class TestSFTPServerController:
        """Manage a test SFTP server instance running on 127.0.0.1:40022 intended to be used as a pytest fixture."""

        logger: Logger = logging.getLogger("TestSFTPServer")
        __test__ = False

        def __init__(self, root: Path) -> None:
            self.__root = root

        def start(
            self,
            username: str = 'test_user',
            password: str = 'test_pass',
            key_only: bool = False,
            log_level: int = logging.DEBUG,
        ) -> TestSFTPFileSystem:
            """Start the test SFTP server.

            :param username: Username for test server, defaults to 'test_user'
            :param password: Password for the test server, defaults to 'test_pass'
            :param key_only: Whether only key authentication should be enabled, this
            will allow the user to authenticate with any key, defaults to False
            :param log_level: _description_, defaults to logging.INFO
            :return: _description_
            """
            logger.setLevel(log_level)

            self.__username = username
            self.__password = password
            self.__key_only = key_only

            self.__server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            self.__server_socket.bind((ADDRESS, PORT))
            self.__server_socket.listen(10)

            self.__thread = threading.Thread(target=self.__run_server, args=())
            self.__thread.daemon = True
            self.__thread.start()

            self.__fs = TestSFTPFileSystem(self.__root, username)
            return self.__fs

        def __run_server(self):
            logger.debug('Starting sftp server 127.0.0.1:40022 with root fs at %s', self.__root)
            try:
                conn, addr = self.__server_socket.accept()

                host_key = RSAKey.from_private_key_file('test_sftp_server.key')
                transport = Transport(conn)
                transport.add_server_key(host_key)
                transport.set_subsystem_handler('sftp', SFTPServer, TestSFTPServer, self.__fs)

                server = TestServer(
                    username=self.__username, password=self.__password, key_only=self.__key_only
                )
                transport.start_server(server=server)

                # TODO: Things break if we don't assign this to something?
                channel = transport.accept()  # noqa: F841

                while transport.is_active():
                    time.sleep(1)
            except ConnectionAbortedError:
                pass
            except Exception as e:
                logger.critical(e, exc_info=True)

        def kill(self) -> None:
            with contextlib.suppress(OSError):
                self.__server_socket.shutdown(socket.SHUT_RDWR)
            self.__server_socket.close()
            logger.setLevel(logging.INFO)

    class TestSFTPFileSystem:
        """Provides access to the filesystem on a :class: StubSFTPServer instance."""

        __test__ = False

        def __init__(self, root: Path, username: str) -> None:
            self.__root = root
            self.__cwd = None
            self.__home = self.create_dir(f'/home/{username}')

        def create_file(self, path: str, size: int = 0) -> Path:
            """Create a file on the :class: `StubSFTPServer` instance.

            If the path is relative it will be created realative to the users home directory

            :param path: The path of the file to create absolute or relative
            :param size: The size in bytes of the file to create, defaults to 0
            :raises ValueError: if it's not possible to canoncalize the path
            :return: An :class: `pathlib.Path` of file created.

            """
            canonicalized: Path = self.canonicalize(path)
            canonicalized.parent.mkdir(parents=True, exist_ok=True)
            with open(canonicalized, 'wb') as file:
                file.write(b'\0' * size)
            return canonicalized

        def create_dir(self, path: str) -> Path:
            """Create a dir on the :class:`StubSFTPServer` instance.

            If the path is relative it will be created in relation to the users home directory

            :param path: The path of the dir to create absolute or relative.
            :raises ValueError: if it's not possible to canoncalize the path
            :returns: An :class:`pathlib.Path` of file created.
            """
            canonicalized: Path = self.canonicalize(path)
            canonicalized.mkdir(parents=True, exist_ok=True)
            return canonicalized

        def create_symlink(self, path: str, target: Path) -> Path:
            """Create a symlink on the :class:`StubSFTPServer` instance.

            If the path or target is relative, it will be done so in relation to the
            users home directory.

            :param path: The path of the symlink to create absolute or relative
            :param target:  The path of the target of the symlink, either absolute or relative
            :raises ValueError: if it's not possible to canoncalize the path or target
            :return: An :class:`pathlib.Path` of the symlink created.
            """
            canonicalized: Path = self.canonicalize(path)
            canonicalized.parent.mkdir(parents=True, exist_ok=True)

            # TODO(kingamajick): check that the target is with in the server
            canonicalized.symlink_to(target, target.is_dir())
            return canonicalized

        def canonicalize(self, path: str, resolve: bool = True) -> Path:
            """Canonicalizes the given SFTP path to the local file system either from the cwd, or the user home if none is set.

            :param path: The path to canonicalize.
            :param resolve: If symlinks shoul be resovled.
            :raises ValueError: If the path or taget is relative and would take return a directory outside the SFTP filesytem.
            :return: An :class:`pathlib.Path` of the canonicalized path.
            """
            canonicalized: Path
            if PurePosixPath(path).is_absolute():
                path = path[1:]
                canonicalized = Path(posixpath.normpath((self.__root / path).as_posix()))
            else:
                canonicalized = Path(posixpath.normpath((self.__cwd or self.__home) / path))

            if self.__root == canonicalized or self.__root in canonicalized.parents:
                return canonicalized.resolve() if resolve else canonicalized
            raise ValueError(f'Unable to canoicalize {path}')

        def root(self) -> Path:
            return self.__root

        def home(self) -> Path:
            return self.__home

    class TestServer(ServerInterface):
        """Handlers authentication to the test server."""

        __test__ = False

        def __init__(self, username: str, password: str, key_only: bool) -> None:
            super().__init__()
            self.__username = username
            self.__password = password
            self.__key_only = key_only

        def check_auth_password(self, username: str, password: str) -> int:
            if self.__username == username and self.__password == password:
                return AUTH_SUCCESSFUL
            return AUTH_FAILED

        def check_auth_publickey(self, username: str, key) -> int:
            if key:
                return AUTH_SUCCESSFUL
            return AUTH_FAILED

        def check_channel_request(self, kind: str, chanid: int):
            return OPEN_SUCCEEDED

        def get_allowed_auths(self, username: str) -> str:
            if self.__key_only:
                return 'publickey'
            return 'password, publickey'

    class TestSFTPHandle(SFTPHandle):
        __test__ = False

        def __init__(self, filename: str, read_file, write_file, flags: int = 0) -> None:
            super().__init__(flags)
            # Note these names are used in the default SFTPHandle, hense no __ to
            # indicate private
            self.filename = filename
            self.readfile = read_file
            self.writefile = write_file

        def stat(self):
            logger.debug('stat() on %s', self.filename)
            try:
                return SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))
            except OSError as e:
                return TestSFTPHandle.log_and_return_error_code(e)

        def chattr(self, attr):
            logger.debug('chattr(%s) on %s', attr, self.filename)
            # python doesn't have equivalents to fchown or fchmod, so we have to
            # use the stored filename
            try:
                SFTPServer.set_file_attr(self.filename, attr)
            except OSError as e:
                return TestSFTPHandle.log_and_return_error_code(e)
            return SFTP_OK

        @staticmethod
        def log_and_return_error_code(e: OSError) -> int:
            logger.critical(e, exc_info=True)
            return SFTPServer.convert_errno(e.errno)

    class TestSFTPServer(SFTPServerInterface):
        __test__ = False

        def __init__(
            self, server: ServerInterface, fs: TestSFTPFileSystem, *larg, **kwarg
        ) -> None:
            super().__init__(server, *larg, **kwarg)
            self.__fs = fs

        def session_started(self):
            logger.debug('session_started')

        def session_ended(self):
            logger.debug('session_ended')

        def open(self, path: str, flags: int, attr: SFTPAttributes) -> SFTPHandle | int:
            logger.debug('open(%s, %s, %s)', path, flags, attr)

            canonicalized_path: Path = self.__fs.canonicalize(path)
            try:
                # Ensure Binary mode.
                flags |= getattr(os, 'O_BINARY', 0)
                mode = attr.st_mode if attr.st_mode else 0o666  # rw-rw-rw-
                fd = os.open(canonicalized_path, flags, mode)
            except OSError as e:
                logger.critical(e, exc_info=True)
                return SFTPServer.convert_errno(e.errno)

            if (flags & os.O_CREAT) and (attr is not None):
                attr._flags &= ~attr.FLAG_PERMISSIONS
                SFTPServer.set_file_attr(path, attr)
            if flags & os.O_WRONLY:
                file_mode = "ab" if flags & os.O_APPEND else "wb"
            elif flags & os.O_RDWR:
                file_mode = "a+b" if flags & os.O_APPEND else "r+b"
            else:
                # O_RDONLY
                file_mode = 'rb'
            try:
                file = os.fdopen(fd, file_mode)
            except OSError as e:
                return TestSFTPServer.log_and_return_error_code(e)
            return TestSFTPHandle(path, file, file, flags)

        def list_folder(self, path: str):
            logger.debug('list_folder(%s)', path)

            canonicalized_path: Path = self.__fs.canonicalize(path)
            try:
                out = []
                for filename in os.listdir(canonicalized_path):
                    attr = SFTPAttributes.from_stat(
                        os.stat(os.path.join(canonicalized_path, filename))
                    )
                    attr.filename = filename
                    out.append(attr)
            except OSError as e:
                return TestSFTPServer.log_and_return_error_code(e)
            return out

        def stat(self, path: str) -> SFTPAttributes | int:
            logger.debug('stat(%s)', path)

            try:
                return SFTPAttributes.from_stat(os.stat(self.__fs.canonicalize(path)))
            except OSError as e:
                return TestSFTPServer.log_and_return_error_code(e)

        def lstat(self, path: str) -> SFTPAttributes | int:
            logger.debug('lstat(%s)', path)
            try:
                return SFTPAttributes.from_stat(
                    os.lstat(self.__fs.canonicalize(path, resolve=False))
                )
            except OSError as e:
                return TestSFTPServer.log_and_return_error_code(e)

        def remove(self, path: str) -> int:
            logger.debug('remove(%s)', path)
            try:
                self.__fs.canonicalize(path, resolve=False).unlink()
            except OSError as e:
                return TestSFTPServer.log_and_return_error_code(e)
            return SFTP_OK

        def rename(self, oldpath: str, newpath: str) -> int:
            logger.debug('rename(%s, %s)', oldpath, newpath)
            """
            Rename (or move) a file.  The SFTP specification implies that this
            method can be used to move an existing file into a different folder,
            and since there's no other (easy) way to move files via SFTP, it's
            probably a good idea to implement "move" in this method too, even for
            files that cross disk partition boundaries, if at all possible.
            .. note:: You should return an error if a file with the same name as
                ``newpath`` already exists.  (The rename operation should be
                non-desctructive.)
            .. note::
                This method implements 'standard' SFTP ``RENAME`` behavior; those
                seeking the OpenSSH "POSIX rename" extension behavior should use
                `posix_rename`.
            :param str oldpath:
                the requested path (relative or absolute) of the existing file.
            :param str newpath: the requested new path of the file.
            :return: an SFTP error code `int` like ``SFTP_OK``.
            """
            return SFTP_OP_UNSUPPORTED

        def posix_rename(self, oldpath: str, newpath: str) -> int:
            logger.debug('posix_rename(%s, %s)', oldpath, newpath)
            """
            Rename (or move) a file, following posix conventions. If newpath
            already exists, it will be overwritten.
            :param str oldpath:
                the requested path (relative or absolute) of the existing file.
            :param str newpath: the requested new path of the file.
            :return: an SFTP error code `int` like ``SFTP_OK``.
            :versionadded: 2.2
            """
            return SFTP_OP_UNSUPPORTED

        def mkdir(self, path: str, attr: SFTPAttributes) -> int:
            logger.debug('mkdir(%s, %s)', path, attr)
            """
            Create a new directory with the given attributes.  The ``attr``
            object may be considered a "hint" and ignored.
            The ``attr`` object will contain only those fields provided by the
            client in its request, so you should use ``hasattr`` to check for
            the presence of fields before using them.  In some cases, the ``attr``
            object may be completely empty.
            :param str path:
                requested path (relative or absolute) of the new folder.
            :param .SFTPAttributes attr: requested attributes of the new folder.
            :return: an SFTP error code `int` like ``SFTP_OK``.
            """
            try:
                self.__fs.canonicalize(path).mkdir()
            except OSError as e:
                return TestSFTPServer.log_and_return_error_code(e)
            return SFTP_OK

        def rmdir(self, path: str) -> int:
            logger.debug('rmdir(%s)', path)
            """
            Remove a directory if it exists.  The ``path`` should refer to an
            existing, empty folder -- otherwise this method should return an
            error.
            :param str path:
                requested path (relative or absolute) of the folder to remove.
            :return: an SFTP error code `int` like ``SFTP_OK``.
            """
            try:
                self.__fs.canonicalize(path).rmdir()
            except OSError as e:
                return TestSFTPServer.log_and_return_error_code(e)
            return SFTP_OK

        def chattr(self, path: str, attr: SFTPAttributes) -> int:
            logger.debug('chattr(%s, %s)', path, attr)
            """
            Change the attributes of a file.  The ``attr`` object will contain
            only those fields provided by the client in its request, so you
            should check for the presence of fields before using them.
            :param str path:
                requested path (relative or absolute) of the file to change.
            :param attr:
                requested attributes to change on the file (an `.SFTPAttributes`
                object)
            :return: an error code `int` like ``SFTP_OK``.
            """
            return SFTP_OP_UNSUPPORTED

        def readlink(self, path: str) -> str | int:
            logger.debug('readlink(%s)', path)
            """
            Return the target of a symbolic link (or shortcut) on the server.
            If the specified path doesn't refer to a symbolic link, an error
            should be returned.
            :param str path: path (relative or absolute) of the symbolic link.
            :return:
                the target `str` path of the symbolic link, or an error code like
                ``SFTP_NO_SUCH_FILE``.
            """
            return SFTP_OP_UNSUPPORTED

        def symlink(self, target_path: str, path: str) -> int:
            logger.debug('symlink(%s, %s)', target_path, path)
            """
            Create a symbolic link on the server, as new pathname ``path``,
            with ``target_path`` as the target of the link.
            :param str target_path:
                path (relative or absolute) of the target for this new symbolic
                link.
            :param str path:
                path (relative or absolute) of the symbolic link to create.
            :return: an error code `int` like ``SFTP_OK``.
            """
            return SFTP_OP_UNSUPPORTED

        def canonicalize(self, path: str) -> str:
            logger.debug('canonicalize(%s)', path)
            return (
                '/'
                + self.__fs.canonicalize(path).resolve().relative_to(self.__fs.root()).as_posix()
            )

        @staticmethod
        def log_and_return_error_code(e: OSError) -> int:
            logger.critical(e, exc_info=True)
            return SFTPServer.convert_errno(e.errno)
