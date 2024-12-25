import filecmp
from pathlib import Path

import pytest
from jinja2 import Template

from .test_sftp_server import TestSFTPFileSystem, TestSFTPServerController


@pytest.mark.xdist_group(name="sftp")
class TestSftpDownload:
    _config = """
        templates:
          anchors:
            _base_sftp_upload: &base_sftp_upload
                host: 127.0.0.1
                port: 40022
                to: './uploaded'
                host_key:
                  key_type: 'ssh-rsa'
                  public_key: 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj'
                socket_timeout_sec: 2
                connection_tries: 1
            _sftp_basic_auth: &sftp_basic_auth
                username: test_user
                password: test_pass

        tasks:
          sftp_upload_file:
            filesystem:
              path:
                - {{ to_upload_path }}
            accept_all: True
            sftp_upload:
              <<: *base_sftp_upload
              <<: *sftp_basic_auth
              delete_origin: False

          sftp_upload_dir:
            filesystem:
              path:
                - {{ to_upload_path }}
            accept_all: True
            sftp_upload:
              <<: *base_sftp_upload
              <<: *sftp_basic_auth
              delete_origin: False

          sftp_upload_file_delete_origin:
            filesystem:
              path:
                - {{ to_upload_path }}
            accept_all: True
            sftp_upload:
              <<: *base_sftp_upload
              <<: *sftp_basic_auth
              delete_origin: True

          sftp_upload_dir_delete_origin:
            filesystem:
              path:
                - {{ to_upload_path }}
            accept_all: True
            sftp_upload:
              <<: *base_sftp_upload
              <<: *sftp_basic_auth
              delete_origin: False

          sftp_upload_key_only:
            filesystem:
              path:
                - {{ to_upload_path }}
            accept_all: True
            sftp_upload:
                <<: *base_sftp_upload
                username: test_user
                private_key: 'test_sftp_user_key'
                private_key_pass: 'password'
    """

    @pytest.fixture
    def to_upload_path(self, tmp_path: Path):
        to_upload_path = tmp_path / 'to_upload'
        to_upload_path.mkdir()
        return to_upload_path

    @pytest.fixture
    def config(self, to_upload_path: Path):
        return Template(self._config).render({'to_upload_path': str(to_upload_path)})

    @pytest.fixture
    def sftp_fs(self, sftp: TestSFTPServerController) -> TestSFTPFileSystem:
        return sftp.start()

    @pytest.fixture
    def remote(self, sftp_fs: TestSFTPFileSystem):
        return sftp_fs.home() / 'uploaded'

    def test_sftp_upload_file(self, execute_task, to_upload_path: Path, remote: Path):
        local_file: Path = TestSftpDownload.create_file(to_upload_path, 'file.mkv', 100)

        execute_task('sftp_upload_file')
        assert filecmp.cmp(local_file, remote / 'file.mkv')

    def test_sftp_upload_dir(self, execute_task, to_upload_path: Path, remote: Path):
        local_dir: Path = TestSftpDownload.create_dir(to_upload_path, 'dir')
        TestSftpDownload.create_file(to_upload_path, 'dir/file1.mkv', 100)
        TestSftpDownload.create_file(to_upload_path, 'dir/nested/file2.mkv', 100)

        execute_task('sftp_upload_dir')

        assert filecmp.dircmp(local_dir, remote / 'dir')

    def test_sftp_upload_file_delete_origin(
        self, execute_task, to_upload_path: Path, remote: Path
    ):
        local_file: Path = TestSftpDownload.create_file(to_upload_path, 'file.mkv', 100)

        execute_task('sftp_upload_file_delete_origin')
        assert not local_file.exists()

    @pytest.mark.skip(
        reason='No attempt is made by the sftp_upload plugin to remove the local dir)'
    )
    def test_sftp_upload_dir_delete_origin(self, execute_task, to_upload_path: Path, remote: Path):
        local_dir: Path = TestSftpDownload.create_dir(to_upload_path, 'dir')
        TestSftpDownload.create_file(to_upload_path, 'dir/file1.mkv', 100)
        TestSftpDownload.create_file(to_upload_path, 'dir/nested/file2.mkv', 100)

        execute_task('sftp_upload_dir_delete_origin')

        assert not local_dir.exists()

    def test_sftp_upload_file_with_key(
        self, execute_task, to_upload_path: Path, sftp: TestSFTPServerController
    ):
        sftp_fs = sftp.start(key_only=True)
        remote = sftp_fs.home() / 'uploaded'
        local_file: Path = TestSftpDownload.create_file(to_upload_path, 'file.mkv', 100)

        execute_task('sftp_upload_key_only')
        assert filecmp.cmp(local_file, remote / 'file.mkv')

    @staticmethod
    def create_file(root: Path, path: str, size: int = 0) -> Path:
        file_path = root / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'wb') as file:
            file.write(b'\0' * size)
        return file_path

    @staticmethod
    def create_dir(root: Path, path: str) -> Path:
        dir_path = root / path
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
