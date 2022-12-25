# coding=utf-8
from pathlib import Path
from typing import Callable

import pytest

from flexget.entry import Entry
from flexget.task import Task, TaskAbort

from .test_sftp_server import TestSFTPFileSystem, TestSFTPServerController


class TestSftpList:
    config = """
        templates:
          anchors:
            _base_sftp_list: &base_sftp_list
                host: 127.0.0.1
                port: 40022
                host_key:
                  key_type: 'ssh-rsa'
                  public_key: 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj'
                socket_timeout_sec: 2
                connection_tries: 1
            _sftp_basic_auth: &sftp_basic_auth
                username: test_user
                password: test_pass

        tasks:
          sftp_list_bad_login:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth

          sftp_list_files:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth

          sftp_list_files_absolute:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              dirs:
                - '/downloads'
          
          sftp_list_files_recursive:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              recursive: True

          sftp_list_dirs:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              files_only: False

          sftp_list_dirs_recursive:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              files_only: False
              recursive: True

          sftp_list_symlink:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth

          sftp_list_symlink_recursive:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              recursive: True

          sftp_list_size:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              files_only: False
              get_size: True
              recursive: True

          sftp_list_key:
            sftp_list:
              <<: *base_sftp_list
              username: test_user
              private_key: 'test_sftp_user_key'
              private_key_pass: 'password'
    """

    @pytest.fixture
    def sftp_fs(self, sftp: TestSFTPServerController) -> TestSFTPFileSystem:
        return sftp.start()

    def test_sftp_list_bad_login(
        self, execute_task: Callable[..., Task], sftp: TestSFTPServerController
    ):
        sftp.start(username='foo', password='bar')

        with pytest.raises(TaskAbort) as ex:
            task = execute_task('sftp_list_bad_login')

        assert ex.value.reason == 'Failed to connect to 127.0.0.1'

    def test_sftp_list_files(self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem):
        sftp_fs.create_file('file.mkv')

        task = execute_task('sftp_list_files')
        assert task.find_entry(title='file.mkv'), 'file.mkv not found'

    def test_sftp_list_files(self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem):
        sftp_fs.create_file('file.mkv')

        task = execute_task('sftp_list_files')
        assert task.find_entry(title='file.mkv'), 'file.mkv not found'

    def test_sftp_list_files_recursive_false(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('dir/file.mkv')

        task = execute_task('sftp_list_files')
        assert not task.find_entry(title='file.mkv'), 'dir/file.mkv found when not recusive'

    def test_sftp_list_files_recursive_true(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('dir/file.mkv')

        task = execute_task('sftp_list_files_recursive')
        assert task.find_entry(title='file.mkv'), 'dir/file.mkv not found'

    def test_sftp_list_dirs(self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem):
        sftp_fs.create_dir('dir')

        task = execute_task('sftp_list_dirs')
        assert task.find_entry(title='dir'), 'dir dir not found'

    def test_sftp_list_dirs_recursive_false(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_dir('dir/nested')

        task = execute_task('sftp_list_dirs')
        assert not task.find_entry(title='nested'), 'dir/nested found when not recusive'

    def test_sftp_list_dirs_recursive_true(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_dir('dir/nested')

        task = execute_task('sftp_list_dirs_recursive')
        assert task.find_entry(title='nested'), 'dir/nested not found when recusive'

    def test_sftp_list_file_size(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('file.mkv', 24)

        task = execute_task('sftp_list_size')
        assert (
            task.find_entry(title='file.mkv')['content_size'] == 24
        ), 'file should have size of 24'

    def test_sftp_list_dir_size(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('dir/file1.mkv', 40)
        sftp_fs.create_file('dir/file2.mkv', 60)

        task = execute_task('sftp_list_size')
        assert task.find_entry(title='dir')['content_size'] == 100, 'dir should have size of 100'

    def test_sftp_list_symlink_file(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_symlink('file.mkv', sftp_fs.create_file('target.mkv', 100))

        task = execute_task('sftp_list_symlink')
        assert task.find_entry(title='file.mkv'), 'file.mkv not found'

    def test_sftp_list_uses_private_key_auth(
        self, execute_task: Callable[..., Task], sftp: TestSFTPServerController
    ):
        sftp_fs: TestSFTPFileSystem = sftp.start(key_only=True)
        sftp_fs.create_file('file.mkv')

        task = execute_task('sftp_list_key')

    def test_sftp_list_private_key_set_on_entry(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('file.mkv')

        task = execute_task('sftp_list_key')
        assert task.find_entry(title='file.mkv')['private_key'] == 'test_sftp_user_key'

    def test_sftp_list_private_key_pass_set_on_entry(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('file.mkv')

        task = execute_task('sftp_list_key')
        assert task.find_entry(title='file.mkv')['private_key_pass'] == 'password'

    def test_sftp_list_host_key_set_on_entry(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('file.mkv')

        task = execute_task('sftp_list_key')
        assert task.find_entry(title='file.mkv')['host_key'] == {
            'key_type': 'ssh-rsa',
            'public_key': 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj',
        }
