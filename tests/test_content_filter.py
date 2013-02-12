from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase, with_filecopy


class TestContentFilter(FlexGetBase):

    __yaml__ = """
        tasks:
          test_reject1:
            mock:
              - {title: 'test', file: 'test_reject1.torrent'}
            accept_all: yes
            content_filter:
              reject: '*.iso'

          test_reject2:
            mock:
              - {title: 'test', file: 'test_reject2.torrent'}
            accept_all: yes
            content_filter:
              reject: '*.avi'

          test_require1:
            mock:
              - {title: 'test', file: 'test_require1.torrent'}
            accept_all: yes
            content_filter:
              require:
                - '*.bin'
                - '*.iso'

          test_require2:
            mock:
              - {title: 'test', file: 'test_require2.torrent'}
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
              - {title: 'test', url: 'http://localhost/', file: 'test.torrent'}
            accept_all: yes
            content_filter:
              reject: ['*.iso']
    """

    @with_filecopy('test.torrent', 'test_reject1.torrent')
    def test_reject1(self):
        """Content Filter: torrent with min size"""
        self.execute_task('test_reject1')
        assert self.task.find_entry('rejected', title='test'), \
            'should have rejected, contains *.iso'

    @with_filecopy('test.torrent', 'test_reject2.torrent')
    def test_reject2(self):
        """Content Filter: torrent with max size"""
        self.execute_task('test_reject2')
        assert self.task.find_entry('accepted', title='test'), \
            'should have accepted, doesn\t contain *.avi'

    @with_filecopy('test.torrent', 'test_require1.torrent')
    def test_require1(self):
        """Content Filter: torrent with min size"""
        self.execute_task('test_require1')
        assert self.task.find_entry('accepted', title='test'), \
            'should have accepted, contains *.iso'

    @with_filecopy('test.torrent', 'test_require2.torrent')
    def test_require2(self):
        """Content Filter: torrent with max size"""
        self.execute_task('test_require2')
        assert self.task.find_entry('rejected', title='test'), \
            'should have rejected, doesn\t contain *.avi'

    @with_filecopy('test.torrent', 'test_strict.torrent')
    def test_strict(self):
        """Content Filter: strict enabled"""
        self.execute_task('test_strict')
        assert self.task.find_entry('rejected', title='test'), \
            'should have rejected non torrent'

    def test_cache(self):
        """Content Filter: caching"""
        self.execute_task('test_cache')

        assert self.task.find_entry('rejected', title='test'), \
            'should have rejected, contains *.iso'

        # Test that remember_rejected rejects the entry before us next time
        self.execute_task('test_cache')
        assert self.task.find_entry('rejected', title='test', rejected_by='remember_rejected'), \
            'should have rejected, content files present from the cache'
