import shutil
from tests import FlexGetBase


class TestTorrentSize(FlexGetBase):

    __yaml__ = """
        feeds:
          test_min:
            mock:
              - {title: 'test', file: 'tests/test_min.torrent'}
            accept_all: yes
            content_size:
              min: 2000

          test_max:
            mock:
              - {title: 'test', file: 'tests/test_max.torrent'}
            accept_all: yes
            content_size:
              max: 10

          test_strict:
            mock:
              - {title: 'test'}
            accept_all: yes
            content_size:
              min: 1
              strict: yes

          test_cache_1:
            mock:
              - {title: 'test', url: 'http://localhost/', file: 'tests/test.torrent'}
            accept_all: yes
            content_size:
              min: 2000

          test_cache_2:
            mock:
              - {title: 'test', url: 'http://localhost/'}
            accept_all: yes
            content_size:
              min: 2000
    """

    testfiles = ['tests/test_min.torrent', 'tests/test_max.torrent', 'tests/test_strict.torrent']

    def setup(self):
        FlexGetBase.setup(self)
        for filename in self.testfiles:
            shutil.copy('tests/test.torrent', filename)

    def test_min(self):
        """Content Size: torrent with min size"""
        self.execute_feed('test_min')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, minimum size'

    def test_max(self):
        """Content Size: torrent with max size"""
        self.execute_feed('test_max')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, maximum size'

    def test_strict(self):
        """Content Size: strict enabled"""
        self.execute_feed('test_strict')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected non torrent'

    def test_cache(self):
        """Content Size: caching"""
        self.execute_feed('test_cache_1')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, too small'

        self.execute_feed('test_cache_2')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, size present from the cache'
