# coding=utf-8
import filecmp
import logging
from pathlib import Path

import pytest
from jinja2 import Template

from .test_sftp_server import TestSFTPFileSystem, TestSFTPServerController


@pytest.mark.usefixtures('tmpdir')
class TestSftpDownload:
    _config = """
        templates:
          anchors:
            _sftp_list: &base_sftp_download
                to: {{ download_path }}
                socket_timeout_sec: 2
                connection_tries: 1

        tasks:
          sftp_download_file:
            mock: 
              - {'title': 'file.mkv', 'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/file.mkv', 'host_key': {
                  'key_type': 'ssh-rsa',
                  'public_key': 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj'
                }}
            accept_all: True
            sftp_download:
              <<: *base_sftp_download
              delete_origin: False

          sftp_download_dir:
            mock: 
              - {'title': 'dir', 'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir', 'host_key': {
                  'key_type': 'ssh-rsa',
                  'public_key': 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj'
                }}
            accept_all: True
            sftp_download:
              to: {{ download_path }}
              delete_origin: False

          sftp_download_dir_recusive:
            mock: 
              - {'title': 'dir', 'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir', 'host_key': {
                  'key_type': 'ssh-rsa',
                  'public_key': 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj'
                }}
            accept_all: True
            sftp_download:
              to: {{ download_path }}
              delete_origin: False
              recursive: True

          sftp_download_file_delete_origin:
            mock: 
              - {'title': 'file.mkv', 'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/file.mkv', 'host_key': {
                  'key_type': 'ssh-rsa',
                  'public_key': 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj'
                }}
            accept_all: True
            sftp_download:
              <<: *base_sftp_download
              delete_origin: True

          sftp_download_dir_delete_origin:
            mock: 
              - {'title': 'dir', 'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir', 'host_key': {
                  'key_type': 'ssh-rsa',
                  'public_key': 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj'
                }}
            accept_all: True
            sftp_download:
              <<: *base_sftp_download
              delete_origin: True
              recursive: True
    """

    @pytest.fixture
    def download_path(self, tmp_path: Path):
        download_path = tmp_path / 'downloads'
        download_path.mkdir()
        return download_path

    @pytest.fixture
    def config(self, download_path: Path):
        return Template(self._config).render({'download_path': str(download_path)})

    @pytest.fixture
    def sftp_fs(self, sftp: TestSFTPServerController) -> TestSFTPFileSystem:
        return sftp.start()

    def test_sftp_download_file(
        self, execute_task, download_path: Path, sftp_fs: TestSFTPFileSystem
    ):
        remote_file: Path = sftp_fs.create_file('file.mkv', 100)

        execute_task('sftp_download_file')
        assert filecmp.cmp(remote_file, download_path / 'file.mkv')

    def test_sftp_download_dir(
        self, execute_task, download_path: Path, sftp_fs: TestSFTPFileSystem
    ):
        remote_file = sftp_fs.create_file('dir/file.mkv', 100)
        sftp_fs.create_file('dir/nested/file.mkv', 100)

        execute_task('sftp_download_dir')
        assert filecmp.dircmp(remote_file, download_path / 'dir/file.mkv')
        assert not (download_path / 'nested/file.mkv').exists()

    def test_sftp_download_dir_recusive(
        self, execute_task, download_path: Path, sftp_fs: TestSFTPFileSystem
    ):
        remote_dir = sftp_fs.create_dir('dir')
        sftp_fs.create_file('dir/file.mkv', 100)
        sftp_fs.create_file('dir/nested/file.mkv', 100)

        execute_task('sftp_download_dir_recusive')
        assert filecmp.dircmp(remote_dir, download_path / 'dir')

    def test_sftp_download_file_and_delete(
        self, execute_task, download_path: Path, sftp_fs: TestSFTPFileSystem
    ):
        remote_file: Path = sftp_fs.create_file('file.mkv', 100)

        execute_task('sftp_download_file_delete_origin')
        assert not remote_file.exists()

    @pytest.mark.skip(
        reason='No attempt is made by the sftp_download plugin to remove the directories)'
    )
    def test_sftp_download_dir_and_delete(
        self, execute_task, download_path: Path, sftp_fs: TestSFTPFileSystem
    ):
        remote_dir = sftp_fs.create_dir('dir')
        sftp_fs.create_file('dir/file.mkv', 100)
        sftp_fs.create_file('dir/nested/file.mkv', 100)

        execute_task('sftp_download_dir_delete_origin')
        assert not remote_dir.exists()
