import pytest


@pytest.mark.filecopy('test.torrent', '__tmp__/')
@pytest.mark.filecopy('multi.torrent', '__tmp__/')
class TestContentFilter:
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

          test_min_files:
            max_reruns: 0
            mock:
              - {title: 'onefile', url: 'http://localhost/', file: '__tmp__/test.torrent'}
              - {title: 'manyfiles', url: 'http://localhost/', file: '__tmp__/multi.torrent'}
            accept_all: yes
            content_filter:
              min_files: 4

          test_max_files:
            max_reruns: 0
            mock:
              - {title: 'onefile', url: 'http://localhost/', file: '__tmp__/test.torrent'}
              - {title: 'manyfiles', url: 'http://localhost/', file: '__tmp__/multi.torrent'}
            accept_all: yes
            content_filter:
              max_files: 3

          test_list_populate_a:
            mock:
              - ubuntu*
            accept_all: yes
            list_add:
              - entry_list: accept-list

          test_list_populate_r:
            mock:
              - flexget*
            accept_all: yes
            list_add:
              - entry_list: accept-list

          test_list_require:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              require:
                from:
                  - entry_list: accept-list

          test_input_require_a:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              require:
                from:
                  - mock: ['ubuntu*']

          test_input_require_r:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              require:
                from:
                  - mock: ['*flexget*']

          test_input_require_all:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              require_all:
                from:
                  - mock: ['*flexget*', 'ubuntu*']

          test_regexp_require_a:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              regexp_mode: yes
              require:
                from:
                  - mock: ['ubuntu']

          test_regexp_require_r:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            accept_all: yes
            content_filter:
              regexp_mode: yes
              require:
                from:
                  - mock: ['flexget']
    """

    def test_reject1(self, execute_task):
        task = execute_task('test_reject1')
        assert task.find_entry('rejected', title='test'), 'should have rejected, contains *.iso'

    def test_reject2(self, execute_task):
        task = execute_task('test_reject2')
        assert task.find_entry('accepted', title='test'), (
            'should have accepted, doesn\'t contain *.avi'
        )

    def test_require1(self, execute_task):
        task = execute_task('test_require1')
        assert task.find_entry('accepted', title='test'), 'should have accepted, contains *.iso'

    def test_require2(self, execute_task):
        task = execute_task('test_require2')
        assert task.find_entry('rejected', title='test'), (
            'should have rejected, doesn\'t contain *.avi'
        )

    def test_require_all1(self, execute_task):
        task = execute_task('test_require_all1')
        assert task.find_entry('accepted', title='test'), (
            'should have accepted, both masks are satisfied'
        )

    def test_require_all2(self, execute_task):
        task = execute_task('test_require_all2')
        assert task.find_entry('rejected', title='test'), (
            'should have rejected, one mask isn\'t satisfied'
        )

    def test_strict(self, execute_task):
        """Content Filter: strict enabled"""
        task = execute_task('test_strict')
        assert task.find_entry('rejected', title='test'), 'should have rejected non torrent'

    def test_cache(self, execute_task):
        """Content Filter: caching"""
        task = execute_task('test_cache')

        assert task.find_entry('rejected', title='test'), 'should have rejected, contains *.iso'

        # Test that remember_rejected rejects the entry before us next time
        task = execute_task('test_cache')
        assert task.find_entry('rejected', title='test', rejected_by='remember_rejected'), (
            'should have rejected, content files present from the cache'
        )

    def test_min_files(self, execute_task):
        task = execute_task('test_min_files')

        assert task.find_entry('rejected', title='onefile'), 'should have rejected, has <4 files'
        assert task.find_entry('accepted', title='manyfiles'), 'should have accepted, >= 4 files'

    def test_max_files(self, execute_task):
        task = execute_task('test_max_files')

        assert task.find_entry('rejected', title='manyfiles'), 'should have rejected, >3 files'
        assert task.find_entry('accepted', title='onefile'), 'should have accepted, has <=3 files'

    def test_list_require_a(self, execute_task):
        execute_task('test_list_populate_a')
        task = execute_task('test_list_require')
        assert task.find_entry('accepted', title='test'), 'should have accepted, contains ubuntu'

    def test_list_require_r(self, execute_task):
        execute_task('test_list_populate_r')
        task = execute_task('test_list_require')
        assert task.find_entry('rejected', title='test'), (
            'should have rejected, mask isn\'t satisfied'
        )

    def test_input_require_a(self, execute_task):
        task = execute_task('test_input_require_a')
        assert task.find_entry('accepted', title='test'), 'should have accepted, contains ubuntu'

    def test_input_require_r(self, execute_task):
        task = execute_task('test_input_require_r')
        assert task.find_entry('rejected', title='test'), (
            'should have rejected, mask isn\'t satisfied'
        )

    def test_input_require_all(self, execute_task):
        task = execute_task('test_input_require_all')
        assert task.find_entry('rejected', title='test'), (
            'should have rejected, one mask isn\'t satisfied'
        )

    def test_regexp_require_a(self, execute_task):
        task = execute_task('test_regexp_require_a')
        assert task.find_entry('accepted', title='test'), 'should have accepted, contains ubuntu'

    def test_regexp_require_r(self, execute_task):
        task = execute_task('test_regexp_require_r')
        assert task.find_entry('rejected', title='test'), (
            'should have rejected, mask isn\'t satisfied'
        )
