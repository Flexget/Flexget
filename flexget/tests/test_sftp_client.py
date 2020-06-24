from typing import List, Dict, Optional
from unittest import mock

import unittest
from unittest.mock import create_autospec

import pysftp
import pytest

from flexget.components.ftp.sftp_client import SftpClient, HandlerBuilder, Handlers, NodeHandler, SftpClientBuilder
from flexget.entry import Entry

host: str = 'localhost'
port: int = 1337
username: str = 'test'
password: str = 'password'
private_key: str = '/home/test/.ssh/id_rsa'
private_key_pass: str = 'keypass'
connection_tries: int = 3

handle_file = mock.create_autospec(Handlers.handle_file)
handle_directory = mock.create_autospec(Handlers.handle_directory)
handle_unknown = mock.create_autospec(Handlers.handle_unknown)


class TestSftpClientBuilder(unittest.TestCase):

    @mock.patch('flexget.components.ftp.sftp_client.HandlerBuilder')
    @mock.patch('flexget.components.ftp.sftp_client.SftpClient')
    @mock.patch('pysftp.Connection')
    def test_build_sftp_client(self, sftp_connection_builder, sftp_client_builder, mock_handler_builder_builder):
        """
        Tests that SftpClient initializes pysftp.Connection correctly
        :param mock_sftp: mock_sftp pysftp.Connection injected by unittest.mock
        :return:
        """
        # Arrange
        url_prefix: str = 'sftp://test:password@localhost:1337/'
        mock_sftp_connection = sftp_connection_builder.return_value
        mock_handler_builder = mock_handler_builder_builder.return_value
        mock_sftp_client = sftp_client_builder.return_value

        # Act
        sftp_client: SftpClient = SftpClientBuilder.build_sftp_client(host=host, username=username, private_key=private_key,
                                            password=password, port=port, private_key_pass=private_key_pass)

        # Assert
        sftp_connection_builder.assert_called_once_with(host=host, username=username, private_key=private_key,
                                                        password=password, port=port, private_key_pass=private_key_pass)

        mock_handler_builder_builder.assert_called_once_with(mock_sftp_connection, url_prefix, private_key,
                                                     private_key_pass)

        sftp_client_builder.assert_called_once_with(mock_sftp_connection, mock_handler_builder, url_prefix)

        self.assertEqual(mock_sftp_client, sftp_client)

    @mock.patch('pysftp.Connection', side_effect=ConnectionRefusedError)
    def test_connection_tries(self, sftp_connection_builder):
        """
        Test that, when an exception is thrown while connecting, the client retries the connection the correct number
        of times and eventually raises the exception
        :param sftp_connection_builder: mock_sftp pysftp.Connection injected by unittest.mock
        :return:
        """
        with self.assertRaises(ConnectionRefusedError):
            # Arrange
            retry_interval_sec: int = 0
            retry_step_sec: int = 0

            # Act
            SftpClientBuilder.build_sftp_client(host, port, username, password, None, None, connection_tries,
                                                retry_interval_sec, retry_step_sec)

            # Assert
            self.assertEqual(sftp_connection_builder.call_count, connection_tries)

    @mock.patch('pysftp.Connection')
    def test_prefix_password(self, mock_sftp):
        """
        Tests that SftpClient builds the SFTP URL prefix correctly given a username and password
        :param mock_sftp: mock_sftp pysftp.Connection injected by unittest.mock
        :return:
        """
        # Arrange
        expected_prefix = 'sftp://test:password@localhost:1337/'

        # Act
        sftp_client: SftpClient = SftpClientBuilder.build_sftp_client(host, port, username, password, None, None)

        # Assert
        self.assertEqual(sftp_client.prefix, expected_prefix)

    @mock.patch('pysftp.Connection')
    def test_prefix_username_no_pass(self, mock_sftp):
        """
        Tests that SftpClient builds the SFTP URL prefix correctly given a username and no password
        :param mock_sftp: mock_sftp pysftp.Connection injected by unittest.mock
        :return:
        """

        # Arrange
        expected_prefix = 'sftp://test@localhost:1337/'

        # Act
        sftp_client: SftpClient = SftpClientBuilder.build_sftp_client(host, port, username, None, None, None)

        # Assert
        self.assertEqual(sftp_client.prefix, expected_prefix)


class TestSftpClient(unittest.TestCase):
    handle_file = mock.create_autospec(Handlers.handle_file)
    handle_directory = mock.create_autospec(Handlers.handle_directory)
    handle_unknown = mock.create_autospec(Handlers.handle_unknown)

    handler_builder = mock.Mock(HandlerBuilder)
    sftp_connection = mock.Mock(pysftp.Connection)

    handler_builder.get_file_handler = mock.Mock(return_value=handle_file)
    handler_builder.get_dir_handler = mock.Mock(return_value=handle_directory)
    handler_builder.get_unknown_handler = mock.Mock(return_value=handle_unknown)

    url_prefix = 'sftp://test:password@localhost:1337/'

    def test_list_directories(self):
        # Arrange
        path_one: str = '/path/to/thing1'
        path_two: str = '/path/to/thing2'
        directories: List[str] = [path_one, path_two]

        recursive: bool = True
        get_size: bool = True
        files_only: bool = True

        # Act
        sftp_client = SftpClient(self.sftp_connection, self.handler_builder, self.url_prefix)
        sftp_client.list_directories(directories, recursive, get_size, files_only)

        # Assert
        # Verify handlers are built correctly
        self.handler_builder.get_dir_handler.assert_called_once_with(get_size, files_only, [])
        self.handler_builder.get_file_handler.assert_called_once_with(get_size, [])
        self.handler_builder.get_unknown_handler.assert_called_once()

        # Verify that pysftp.Connection.walktree() is called correctly
        calls = [mock.call(path_one, self.handle_file, self.handle_directory, self.handle_unknown, recursive),
            mock.call(path_two, self.handle_file, self.handle_directory, self.handle_unknown, recursive)]
        self.sftp_connection.walktree.assert_has_calls(calls)
        self.assertEqual(self.sftp_connection.walktree.call_count, len(directories))
