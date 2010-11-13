import shutil
from tests import FlexGetBase, with_filecopy


class TestContentFilter(FlexGetBase):

    __yaml__ = """
        feeds:
          test_reject1:
            mock:
              - {title: 'test', file: 'tests/test_reject1.torrent'}
            accept_all: yes
            content_filter:
              reject: '*.iso'

          test_reject2:
            mock:
              - {title: 'test', file: 'tests/test_reject2.torrent'}
            accept_all: yes
            content_filter:
              reject: '*.avi'

          test_require1:
            mock:
              - {title: 'test', file: 'tests/test_require1.torrent'}
            accept_all: yes
            content_filter:
              require: '*.iso'

          test_require2:
            mock:
              - {title: 'test', file: 'tests/test_require2.torrent'}
            accept_all: yes
            content_filter:
              require: '*.avi'

          test_strict:
            mock:
              - {title: 'test'}
            accept_all: yes
            content_filter:
              require: '*.iso'
              strict: true

          test_cache:
            mock:
              - {title: 'test', url: 'http://localhost/', file: 'tests/test.torrent'}
            accept_all: yes
            content_filter:
              reject: '*.iso'
    """

    @with_filecopy('tests/test.torrent', 'tests/test_reject1.torrent')
    def test_reject1(self):
        """Content Size: torrent with min size"""
        self.execute_feed('test_reject1')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, contains *.iso'

    @with_filecopy('tests/test.torrent', 'tests/test_reject2.torrent')
    def test_reject2(self):
        """Content Size: torrent with max size"""
        self.execute_feed('test_reject2')
        assert self.feed.find_entry('accepted', title='test'), \
            'should have accepted, doesn\t contain *.avi'

    @with_filecopy('tests/test.torrent', 'tests/test_require1.torrent')
    def test_require1(self):
        """Content Size: torrent with min size"""
        self.execute_feed('test_require1')
        assert self.feed.find_entry('accepted', title='test'), \
            'should have accepted, contains *.iso'

    @with_filecopy('tests/test.torrent', 'tests/test_require2.torrent')
    def test_require2(self):
        """Content Size: torrent with max size"""
        self.execute_feed('test_require2')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, doesn\t contain *.avi'

    @with_filecopy('tests/test.torrent', 'tests/test_strict.torrent')
    def test_strict(self):
        """Content Size: strict enabled"""
        self.execute_feed('test_strict')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected non torrent'

    def test_cache(self):
        """Content Size: caching"""
        self.execute_feed('test_cache')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, contains *.iso'

        # Remove the torrent from the mock entry and make sure it is still rejected
        del self.manager.config['feeds']['test_cache']['mock'][0]['file']
        self.execute_feed('test_cache')
        assert self.feed.find_entry('rejected', title='test'), \
            'should have rejected, content files present from the cache'
