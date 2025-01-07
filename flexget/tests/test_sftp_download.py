import filecmp
import platform
import sys
from pathlib import Path

import pytest
from jinja2 import Template

from .test_sftp_server import TestSFTPFileSystem, TestSFTPServerController


@pytest.mark.skipif(
    platform.system() == 'Windows' and sys.version_info[:2] == (3, 10),
    reason='This test fails intermittently on Windows, Python 3.10.',
)
@pytest.mark.xdist_group(name="sftp")
class TestSftpDownload:
    _config = """
        templates:
          anchors:
            _sftp_download: &base_sftp_download
              to: {{ download_path }}
              socket_timeout_sec: 2
              connection_tries: 1
            _mock_file:
              - &mock_file
                {'title': 'file.mkv', 'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/file.mkv', 'host_key': {
                          'key_type': 'ssh-rsa',
                          'public_key': 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj'
                        }}
            _mock_dir:
              - &mock_dir
                {'title': 'dir', 'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir', 'host_key': {
                          'key_type': 'ssh-rsa',
                          'public_key': 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj'
                        }}

        tasks:
          sftp_download_file:
            mock:
              - *mock_file
            accept_all: True
            sftp_download:
              <<: *base_sftp_download

          sftp_download_dir:
            mock:
              - *mock_dir
            accept_all: True
            sftp_download:
              to: {{ download_path }}

          sftp_download_dir_recusive_true:
            mock:
              - *mock_dir
            accept_all: True
            sftp_download:
              to: {{ download_path }}
              recursive: True

          sftp_download_file_delete_origin_true:
            mock:
              - *mock_file
            accept_all: True
            sftp_download:
              <<: *base_sftp_download
              delete_origin: True

          sftp_download_dir_delete_origin_true_recursive_true:
            mock:
              - *mock_dir
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

        execute_task('sftp_download_dir_recusive_true')
        assert filecmp.dircmp(remote_dir, download_path / 'dir')

    def test_sftp_download_file_and_delete(
        self, execute_task, download_path: Path, sftp_fs: TestSFTPFileSystem
    ):
        remote_file: Path = sftp_fs.create_file('file.mkv', 100)

        execute_task('sftp_download_file_delete_origin_true')
        assert not remote_file.exists()

    def test_sftp_download_file_and_delete_when_symlink_deletes_symlink_only(
        self, execute_task, download_path: Path, sftp_fs: TestSFTPFileSystem
    ):
        remote_file: Path = sftp_fs.create_file('/target.mkv', 100)
        remote_link: Path = sftp_fs.create_symlink('file.mkv', remote_file)

        execute_task('sftp_download_file_delete_origin_true')
        assert remote_file.exists(), '/target.mkv should not have been deleted.'
        assert not remote_link.exists(), 'file.mkv should have been deleted.'

    @pytest.mark.skip(
        reason='No attempt is made by the sftp_download plugin to remove the directories)'
    )
    def test_sftp_download_dir_and_delete(
        self, execute_task, download_path: Path, sftp_fs: TestSFTPFileSystem
    ):
        remote_dir = sftp_fs.create_dir('dir')
        sftp_fs.create_file('dir/file.mkv', 100)
        sftp_fs.create_file('dir/nested/file.mkv', 100)

        execute_task('sftp_download_dir_delete_origin_true_recursive_true')
        assert not remote_dir.exists()
