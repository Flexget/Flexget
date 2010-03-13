import os
import shutil
from tests import FlexGetBase


class TestTorrentSize(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            disable_builtins:
              - seen

        feeds:
          test_min:
            mock:
              - {title: 'test', file: 'tests/test_min.torrent'}
            torrent_size:
              min: 2000

          test_max:
            mock:
              - {title: 'test', file: 'tests/test_max.torrent'}
            torrent_size:
              max: 10
              
          test_strict:
            mock:
              - {title: 'test', file: 'tests/test_strict.torrent'}
            preset:
              - no_global
            mock:
              - {title: 'test'}
            torrent_size:
              min: 1
              strict: yes

    """

    testfiles = ['tests/test_min.torrent', 'tests/test_max.torrent', 'tests/test_strict.torrent']

    def setup(self):
        FlexGetBase.setup(self)
        for filename in self.testfiles:
            shutil.copy('tests/test.torrent', filename)

    def test_min(self):
        self.execute_feed('test_min')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, minimum size'

    def test_max(self):
        self.execute_feed('test_max')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, maximum size'
            
    def test_strict(self):
        self.execute_feed('test_strict')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected non torrent'

        
class TestInfoHash(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'test', file: 'tests/test.torrent'}
    """

    def test_infohash(self):
        self.execute_feed('test')
        assert self.feed.entries[0]['torrent_info_hash'] == '20AE692114DC343C86DF5B07C276E5077E581766', \
            'InfoHash does not match'
