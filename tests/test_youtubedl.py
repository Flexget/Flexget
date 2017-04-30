from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.plugins.attrib import attr
import tempfile
import os

class TestYoutubeDl(FlexGetBase):
    __yaml__ = """
        tasks:
          normal_config:
            mock:
              - {title: 'entry 1', url: 'http://www.youtube.com/watch?v=BaW_jenozKc'}
            accept_all: yes
            youtubedl:
              output: '""" + os.path.join(tempfile.gettempdir(), '%(title)s by %(uploader)s.%(ext)s') + """'
              restrict-filenames: yes
              extract-audio: yes
              keep-video: yes
          small_config:
            mock:
              - {title: 'entry 2', url: 'http://www.youtube.com/watch?v=BaW_jenozKc'}
            accept_all: yes
            youtubedl: """ + tempfile.gettempdir() + """
      """

    @attr(online=True)
    def test_normal_config(self):
        """YoutubeDl plugin: Normal amount of config settings"""
        self.execute_task('normal_config')
        assert not self.task._abort, 'Task should not have aborted'
        assert os.path.isfile(os.path.join(tempfile.gettempdir(), 'youtube-dl_test_video by Philipp_Hagemeister.mp4'))
        assert os.path.isfile(os.path.join(tempfile.gettempdir(), 'youtube-dl_test_video by Philipp_Hagemeister.m4a'))
        os.remove(os.path.join(tempfile.gettempdir(), 'youtube-dl_test_video by Philipp_Hagemeister.mp4')) # cleanup
        os.remove(os.path.join(tempfile.gettempdir(), 'youtube-dl_test_video by Philipp_Hagemeister.m4a'))

    @attr(online=True)
    def test_small_config(self):
        """YoutubeDl plugin: Download path only"""
        self.execute_task('small_config')
        assert not self.task._abort, 'Task should not have aborted'
        assert os.path.isfile(os.path.join(tempfile.gettempdir(), 'BaW_jenozKc.mp4'))
        os.remove(os.path.join(tempfile.gettempdir(), 'BaW_jenozKc.mp4')) # cleanup