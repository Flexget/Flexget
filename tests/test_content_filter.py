from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest


@pytest.mark.usefixtures('tmpdir')
@pytest.mark.filecopy('test.torrent', '__tmp__/')
class TestContentFilter(object):

    config = """
        tasks:
          test_reject1:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              reject: '*.iso'

          test_reject2:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              reject: '*.avi'

          test_require1:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              require:
                - '*.bin'
                - '*.iso'

          test_require2:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              require: '*.avi'

          test_require_all1:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              require_all:
                - 'ubu*'
                - '*.iso'

          test_require_all2:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              require_all:
                - '*.iso'
                - '*.avi'

          test_strict:
            mock:
              - {title: 'test'}
            accept_all: yes
            content_filter:
              require: '*.iso'
              strict: true

          test_cache:
            mock:
              - {title: 'test', url: 'http://localhost/', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              reject: ['*.iso']
    """

    def test_reject1(self, execute_task):
        task = execute_task('test_reject1')
        assert task.find_entry('rejected', title='test'), \
            'should have rejected, contains *.iso'

    def test_reject2(self, execute_task):
        task = execute_task('test_reject2')
        assert task.find_entry('accepted', title='test'), \
            'should have accepted, doesn\t contain *.avi'

    def test_require1(self, execute_task):
        task = execute_task('test_require1')
        assert task.find_entry('accepted', title='test'), \
            'should have accepted, contains *.iso'

    def test_require2(self, execute_task):
        task = execute_task('test_require2')
        assert task.find_entry('rejected', title='test'), \
            'should have rejected, doesn\t contain *.avi'

    def test_require_all1(self, execute_task):
        task = execute_task('test_require_all1')
        assert task.find_entry('accepted', title='test'), \
            'should have accepted, both masks are satisfied'

    def test_require_all2(self, execute_task):
        task = execute_task('test_require_all2')
        assert task.find_entry('rejected', title='test'), \
            'should have rejected, one mask isn\'t satisfied'

    def test_strict(self, execute_task):
        """Content Filter: strict enabled"""
        task = execute_task('test_strict')
        assert task.find_entry('rejected', title='test'), \
            'should have rejected non torrent'

    def test_cache(self, execute_task):
        """Content Filter: caching"""
        task = execute_task('test_cache')

        assert task.find_entry('rejected', title='test'), \
            'should have rejected, contains *.iso'

        # Test that remember_rejected rejects the entry before us next time
        task = execute_task('test_cache')
        assert task.find_entry('rejected', title='test', rejected_by='remember_rejected'), \
            'should have rejected, content files present from the cache'
