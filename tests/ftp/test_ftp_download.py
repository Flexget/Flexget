import filecmp
from pathlib import Path

import pytest


@pytest.mark.require_optional_deps
@pytest.mark.xdist_group(name='ftp')
class TestFtpDownload:
    config = """
        templates:
          global:
            mock:
              - { title: file_to_download, url: to_be_populated }
            accept_all: yes
        tasks:
          keep_origin:
            ftp_download:
              delete_origin: False
              ftp_tmp_path: __tmp__
              use-ssl: False
          delete_origin:
            ftp_download:
              delete_origin: True
              ftp_tmp_path: __tmp__
              use-ssl: False
          use_ssl:
            ftp_download:
              delete_origin: False
              ftp_tmp_path: __tmp__
              use-ssl: True
        """

    def test_keep_origin(self, execute_task, tmp_path, manager, ftpserver):
        ftpserver.reset_tmp_dirs()
        manager.config['templates']['global']['mock'][0]['url'] = ftpserver.put_files(
            'a.txt', style='url', anon=False
        )[0]
        execute_task('keep_origin')
        assert filecmp.cmp(Path(__file__).parent / 'a.txt', tmp_path / 'a.txt')
        assert list(ftpserver.get_file_paths(style='rel_path', anon=False)) == ['a.txt']

    def test_delete_origin(self, execute_task, tmp_path, manager, ftpserver):
        ftpserver.reset_tmp_dirs()
        manager.config['templates']['global']['mock'][0]['url'] = ftpserver.put_files(
            'a.txt', style='url', anon=False
        )[0]
        execute_task('delete_origin')
        assert filecmp.cmp(Path(__file__).parent / 'a.txt', tmp_path / 'a.txt')
        assert list(ftpserver.get_file_paths(style='rel_path', anon=False)) == []

    def test_use_ssl(self, execute_task, tmp_path, manager, ftpserver_TLS):  # noqa: N803
        ftpserver_TLS.reset_tmp_dirs()
        manager.config['templates']['global']['mock'][0]['url'] = ftpserver_TLS.put_files(
            'a.txt', style='url', anon=False
        )[0]
        execute_task('use_ssl')
        assert filecmp.cmp(Path(__file__).parent / 'a.txt', tmp_path / 'a.txt')
        assert list(ftpserver_TLS.get_file_paths(style='rel_path', anon=False)) == ['a.txt']
