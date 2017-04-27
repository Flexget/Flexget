from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest
import sys


# TODO more checks: fail_html, etc.
@pytest.mark.online
@pytest.mark.usefixtures('tmpdir')
class TestDownload(object):
    config = """
        tasks:
          path_and_temp:
            mock:
              - {title: 'entry 1', url: 'http://speedtest.ftp.otenet.gr/files/test100k.db'}
            accept_all: yes
            download:
              path: __tmp__
              temp: __tmp__
          just_path:
            mock:
              - {title: 'entry 2', url: 'http://speedtest.ftp.otenet.gr/files/test100k.db'}
            accept_all: yes
            download:
              path: __tmp__
          just_string:
            mock:
              - {title: 'entry 3', url: 'http://speedtest.ftp.otenet.gr/files/test100k.db'}
            accept_all: yes
            download: __tmp__
      """

    def test_path_and_temp(self, execute_task):
        """Download plugin: Path and Temp directories set"""
        task = execute_task('path_and_temp')
        assert not task.aborted, 'Task should not have aborted'

    def test_just_path(self, execute_task):
        """Download plugin: Path directory set as dict"""
        task = execute_task('just_path')
        assert not task.aborted, 'Task should not have aborted'

    def test_just_string(self, execute_task):
        """Download plugin: Path directory set as string"""
        task = execute_task('just_string')
        assert not task.aborted, 'Task should not have aborted'


# TODO: Fix this test
@pytest.mark.usefixtures('tmpdir')
@pytest.mark.skip(reason='TODO: These are really just config validation tests, and I have config validation turned off'
                         ' at the moment for unit tests due to some problems')
class TestDownloadTemp(object):
    config = """
        tasks:
          temp_wrong_permission:
            mock:
              - {title: 'entry 1', url: 'http://www.speedtest.qsc.de/1kB.qsc'}
            accept_all: yes
            download:
              path: __tmp__
              temp: /root
          temp_non_existent:
            download:
              path: __tmp__
              temp: /a/b/c/non/existent/
          temp_wrong_config_1:
            download:
              path: __tmp__
              temp: no
          temp_wrong_config_2:
            download:
              path: __tmp__
              temp: 3
          temp_empty:
            download:
              path: __tmp__
              temp:
        """

    @pytest.mark.skipif(sys.platform.startswith('win'),
                        reason='Windows does not have a guaranteed "private" directory afaik')
    def test_wrong_permission(self, execute_task):
        """Download plugin: Temp directory has wrong permissions"""
        task = execute_task('temp_wrong_permission', abort_ok=True)
        assert task.aborted

    def test_temp_non_existent(self, execute_task):
        """Download plugin: Temp directory does not exist"""
        task = execute_task('temp_non_existent', abort_ok=True)
        assert task.aborted

    def test_wrong_config_1(self, execute_task):
        """Download plugin: Temp directory config error [1of3]"""
        task = execute_task('temp_wrong_config_1', abort_ok=True)
        assert task.aborted

    def test_wrong_config_2(self, execute_task):
        """Download plugin: Temp directory config error [2of3]"""
        task = execute_task('temp_wrong_config_2', abort_ok=True)
        assert task.aborted

    def test_wrong_config_3(self, execute_task):
        """Download plugin: Temp directory config error [3of3]"""
        task = execute_task('temp_empty', abort_ok=True)
        assert task.aborted


@pytest.mark.online
@pytest.mark.usefixtures('tmpdir')
class TestDownloadAuth(object):
    config = """
        templates:
          download:
            disable: builtins
            mock:
            - title: digest
              url: https://httpbin.org/digest-auth/auth/user/passwd/MD5
            - title: basic
              url: https://httpbin.org/basic-auth/user/passwd
            accept_all: yes
            download:
              path: __tmp__
              temp: __tmp__
            
        tasks:
          no_auth:
            template:
            - download
            
          with_auth:
            template:
            - download
            download_auth:
            - digest-auth:
                username: user
                password: passwd
                type: digest
            - basic-auth:
                username: user
                password: passwd       
    """

    def test_download_auth(self, execute_task):
        """Test download basic and digest auth"""
        task = execute_task('no_auth')
        assert len(task.failed) == 2

        task = execute_task('with_auth')
        assert len(task.accepted) == 2
