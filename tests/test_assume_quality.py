from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.tools import assert_raises
from flexget.task import TaskAbort
import flexget.utils.qualities as qualities

class TestAssumeQuality(FlexGetBase):

    __yaml__ = """
        templates:
          global:
            mock:
              - {title: 'Testfile[h264-720p]'}
              - {title: 'Testfile.1280x720'}
              - {title: 'Testfile.HDTV'}
              - {title: 'Testfile.cam'}
              - {title: 'Testfile.noquality'}
              - {title: 'Testfile.xvid.mp3'}
            accept_all: yes
        tasks:
          test_default:
            assume_quality:
              720p: flac
              h264: 10bit
              HDTV: truehd
              any: 720p h264

          test_simple:
            assume_quality: 720p h264

          test_priority:
            assume_quality:
              720p: mp3
              720p h264: flac
              h264: mp3

          test_matching:
            assume_quality:
              hdtv: 720p

          test_negative_matching:
            assume_quality:
              '!xvid !divx !mp3': 1080p

          test_no_clobber:
            assume_quality:
              720p: xvid

          test_invalid_target:
            assume_quality:
              potato: 720p

          test_invalid_quality:
            assume_quality:
              hdtv: rhubarb

          test_with_series:
            template: no_global
            mock:
            - title: my show S01E01
            assume_quality: 720p
            series:
            - my show:
                quality: 720p
    """

    def test_matching(self):
        self.execute_task('test_matching')
        entry = self.task.find_entry('entries', title='Testfile.HDTV')
        assert entry.get('quality') == qualities.Quality('720p HDTV')

    def test_negative_matching(self):
        self.execute_task('test_negative_matching')
        entry = self.task.find_entry('entries', title='Testfile.HDTV')
        assert entry.get('quality') == qualities.Quality('1080p HDTV')

        entry = self.task.find_entry('entries', title='Testfile.xvid.mp3')
        assert entry.get('quality') == qualities.Quality('xvid mp3')

    def test_no_clobber(self):
        self.execute_task('test_no_clobber')
        entry = self.task.find_entry('entries', title='Testfile[h264-720p]')
        assert entry.get('quality') != qualities.Quality('720p xvid')
        assert entry.get('quality') == qualities.Quality('720p h264')

    def test_default(self):
        self.execute_task('test_default')
        entry = self.task.find_entry('entries', title='Testfile.noquality')
        assert entry.get('quality') == qualities.Quality('720p h264'), 'Testfile.noquality quality not \'720p h264\''

    def test_simple(self):
        self.execute_task('test_simple')
        entry = self.task.find_entry('entries', title='Testfile.noquality')
        assert entry.get('quality') == qualities.Quality('720p h264'), 'Testfile.noquality quality not \'720p h264\''

    def test_priority(self):
        self.execute_task('test_priority')
        entry = self.task.find_entry('entries', title='Testfile[h264-720p]')
        assert entry.get('quality') != qualities.Quality('720p h264 mp3')
        assert entry.get('quality') == qualities.Quality('720p h264 flac')

    def test_invalid_target(self):
        #with assert_raises(TaskAbort): self.execute_task('test_invalid_target')  #Requires Python 2.7
        assert_raises(TaskAbort, self.execute_task, 'test_invalid_target')

    def test_invalid_quality(self):
        #with assert_raises(TaskAbort): self.execute_task('test_invalid_quality')  #Requires Python 2.7
        assert_raises(TaskAbort, self.execute_task, 'test_invalid_quality')

    def test_with_series(self):
        self.execute_task('test_with_series')
        assert self.task.accepted, 'series plugin should have used assumed quality'
