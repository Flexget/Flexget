import os
import shutil
from tests import FlexGetBase


class TestTorrentSize(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            mock:
              - {title: 'test', file: 'tests/copy_of_test.torrent'}
            disable_builtins:
              - seen

        feeds:
          test_min:
            torrent_size:
              min: 2000

          test_max:
            torrent_size:
              max: 10
              
          test_strict:
            preset:
              - no_global
            mock:
              - {title: 'test'}
            torrent_size:
              min: 1
              strict: yes

    """

    def setup(self):
        self.create_copy()
        FlexGetBase.setup(self)

    def create_copy(self):
        if not os.path.exists('tests/copy_of_test.torrent'):
            shutil.copy('tests/test.torrent', 'tests/copy_of_test.torrent')

    def teardown(self):
        FlexGetBase.setup(self)
        if os.path.exists('tests/copy_of_test.torrent'):
            os.remove('tests/copy_of_test.torrent')

    def test_min(self):
        self.create_copy()
        self.execute_feed('test_min')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, minimum size'

    def test_max(self):
        self.create_copy()
        self.execute_feed('test_max')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, maximum size'
            
    def test_strict(self):
        self.create_copy()
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
