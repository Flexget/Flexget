from __future__ import unicode_literals, division, absolute_import
import sys
import tempfile

from nose.plugins.attrib import attr
from nose.plugins.skip import SkipTest

from tests import FlexGetBase

# TODO more checks: fail_html, etc.
class TestDownload(FlexGetBase):
    __yaml__ = """
        tasks:
          path_and_temp:
            mock:
              - {title: 'entry 1', url: 'http://www.speedtest.qsc.de/1kB.qsc'}
            accept_all: yes
            download:
              path: ~/
              temp: """ + tempfile.gettempdir() + """
          just_path:
            mock:
              - {title: 'entry 2', url: 'http://www.speedtest.qsc.de/10kB.qsc'}
            accept_all: yes
            download:
              path: ~/
          just_string:
            mock:
              - {title: 'entry 3', url: 'http://www.speedtest.qsc.de/100kB.qsc'}
            accept_all: yes
            download: ~/
      """

    @attr(online=True)
    def test_path_and_temp(self):
        """Download plugin: Path and Temp directories set"""
        self.execute_task('path_and_temp')
        assert not self.task._abort, 'Task should not have aborted'

    @attr(online=True)
    def test_just_path(self):
        """Download plugin: Path directory set as dict"""
        self.execute_task('just_path')
        assert not self.task._abort, 'Task should not have aborted'

    @attr(online=True)
    def test_just_string(self):
        """Download plugin: Path directory set as string"""
        self.execute_task('just_string')
        assert not self.task._abort, 'Task should not have aborted'


class TestDownloadTemp(FlexGetBase):
    __yaml__ = """
        tasks:
          temp_wrong_permission:
            mock:
              - {title: 'entry 1', url: 'http://www.speedtest.qsc.de/1kB.qsc'}
            accept_all: yes
            download:
              path: ~/
              temp: /root
          temp_non_existent:
            download:
              path: ~/
              temp: /a/b/c/non/existent/
          temp_wrong_config_1:
            download:
              path: ~/
              temp: no
          temp_wrong_config_2:
            download:
              path: ~/
              temp: 3
          temp_empty:
            download:
              path: ~/
              temp:
        """

    def test_wrong_permission(self):
        """Download plugin: Temp directory has wrong permissions"""
        if sys.platform.startswith('win'):
            raise SkipTest  # TODO: Windows doesn't have a guaranteed 'private' directory afaik
        self.execute_task('temp_wrong_permission', True)
        assert self.task._abort_reason == 'Not allowed to write to temp directory `/root`'

    def test_temp_non_existent(self):
        """Download plugin: Temp directory does not exist"""
        self.execute_task('temp_non_existent', True)
        assert self.task._abort_reason == '[/download/temp] `/a/b/c/non/existent/` does not exist'

    def test_wrong_config_1(self):
        """Download plugin: Temp directory config error [1of3]"""
        self.execute_task('temp_wrong_config_1', True)
        assert self.task._abort_reason == '[/download/temp] Got `False`, expected: string'

    def test_wrong_config_2(self):
        """Download plugin: Temp directory config error [2of3]"""
        self.execute_task('temp_wrong_config_2', True)
        assert self.task._abort_reason == '[/download/temp] Got `3`, expected: string'

    def test_wrong_config_3(self):
        """Download plugin: Temp directory config error [3of3]"""
        self.execute_task('temp_empty', True)
        assert self.task._abort_reason == '[/download/temp] Got `None`, expected: string'
