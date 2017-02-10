from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin


class TestListInterface(object):
    config = """
        templates:
          global:
            disable: [seen]
            metainfo_series: yes

        tasks:
          list_get:
            series_list: test_list

          list_1_get:
            series_list: list 1

          list_2_get:
            series_list: list 2

          test_list_add:
            mock:
              - {title: 'New.Series.S01E01', url: "http://mock.url/file1.torrent"}
              - {title: 'Other.Series.S01E01', url: "http://mock.url/file2.torrent"}
            accept_all: yes
            list_add:
              - series_list: test_list

          list_1_add:
            mock:
              - {title: 'New.Series.S01E01', url: "http://mock.url/file1.torrent"}
              - {title: 'Other.Series.S01E01', url: "http://mock.url/file2.torrent"}
            accept_all: yes
            list_add:
              - series_list: list 1

          list_2_add:
            mock:
              - {title: 'Cool.Show.S01E01', url: "http://mock.url/file1.torrent"}
            accept_all: yes
            list_add:
              - series_list: list 2

          test_multiple_list_add:
            mock:
              - {title: 'New.Series.S01E01', url: "http://mock.url/file1.torrent"}
              - {title: 'Other.Series.S01E01', url: "http://mock.url/file2.torrent"}
            accept_all: yes
            list_add:
              - series_list: list 1
              - series_list: list 2

          test_list_accept_with_remove:
            mock:
              - {title: 'New.Series.S01E01', url: "http://mock.url/file1.torrent"}
              - {title: 'Other.Series.S01E01', url: "http://mock.url/file2.torrent"}
              - {title: 'Cool.Show.S01E01', url: "http://mock.url/file2.torrent"}
            list_match:
              from:
                - series_list: test_list

          test_list_accept_without_remove:
            mock:
              - {title: 'New.Series.S01E01', url: "http://mock.url/file1.torrent"}
              - {title: 'Other.Series.S01E01', url: "http://mock.url/file2.torrent"}
              - {title: 'Cool.Show.S01E01', url: "http://mock.url/file2.torrent"}
            list_match:
              from:
                - series_list: test_list
              remove_on_match: no

          test_multiple_list_accept_with_remove:
            mock:
              - {title: 'New.Series.S01E01', url: "http://mock.url/file1.torrent"}
              - {title: 'Other.Series.S01E01', url: "http://mock.url/file2.torrent"}
              - {title: 'Cool.Show.S01E01', url: "http://mock.url/file2.torrent"}
            list_match:
              from:
                - series_list: list 1
                - series_list: list 2

          test_multiple_list_accept_without_remove:
            mock:
              - {title: 'New.Series.S01E01', url: "http://mock.url/file1.torrent"}
              - {title: 'Other.Series.S01E01', url: "http://mock.url/file2.torrent"}
              - {title: 'Cool.Show.S01E01', url: "http://mock.url/file2.torrent"}
            list_match:
              from:
                - series_list: list 1
                - series_list: list 2
              remove_on_match: no

          test_list_remove:
            mock:
              - {title: 'New.Series.S01E01', url: "http://mock.url/file1.torrent"}
            accept_all: yes
            list_remove:
              - series_list: test_list

          test_list_reject:
            mock:
              - {title: 'New.Series.S01E01', url: "http://mock.url/file1.torrent"}
              - {title: 'Cool.Show.S01E01', url: "http://mock.url/file2.torrent"}
            list_match:
              from:
                - series_list: test_list
              action: reject

          test_allowed_identifiers:
            mock:
              - {title: 'title 1',
                 url: "http://mock.url/file1.torrent",
                 tvdb_id: "208111",
                 fake_id_name: "123abc"
                 }
            accept_all: yes
            list_add:
              - series_list: test_list

          test_list_accept_for_real_title:
            mock:
              - {title: 'New.Series.S01E10.720p.BluRay.x264-Group'}
            list_match:
              from:
                - series_list: test_list
    """

    def test_list_add(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

    def test_allowed_identifiers(self, execute_task):
        task = execute_task('test_allowed_identifiers')
        assert len(task.entries) == 1

        task = execute_task('list_get')
        assert len(task.entries) == 1

        assert task.find_entry(tvdb_id='208111')
        assert not task.find_entry(fake_id_name='123abc')

    def test_multiple_list_add(self, execute_task):
        task = execute_task('test_multiple_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_1_get')
        assert len(task.entries) == 2

        task = execute_task('list_2_get')
        assert len(task.entries) == 2

    def test_list_accept_with_remove(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

        task = execute_task('test_list_accept_with_remove')
        assert len(task.all_entries) == 3
        assert len(task.accepted) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 0

    def test_list_accept_without_remove(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

        task = execute_task('test_list_accept_without_remove')
        assert len(task.all_entries) == 3
        assert len(task.accepted) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

    def test_multiple_list_accept_with_remove(self, execute_task):
        task = execute_task('list_1_add')
        assert len(task.entries) == 2

        task = execute_task('list_2_add')
        assert len(task.entries) == 1

        task = execute_task('list_1_get')
        assert len(task.entries) == 2

        task = execute_task('list_2_get')
        assert len(task.entries) == 1

        task = execute_task('test_multiple_list_accept_with_remove')
        assert len(task.accepted) == 3

        task = execute_task('list_1_get')
        assert len(task.entries) == 0

        task = execute_task('list_2_get')
        assert len(task.entries) == 0

    def test_multiple_list_accept_without_remove(self, execute_task):
        task = execute_task('list_1_add')
        assert len(task.entries) == 2

        task = execute_task('list_2_add')
        assert len(task.entries) == 1

        task = execute_task('list_1_get')
        assert len(task.entries) == 2

        task = execute_task('list_2_get')
        assert len(task.entries) == 1

        task = execute_task('test_multiple_list_accept_without_remove')
        assert len(task.accepted) == 3

        task = execute_task('list_1_get')
        assert len(task.entries) == 2

        task = execute_task('list_2_get')
        assert len(task.entries) == 1

    def test_list_remove(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

        task = execute_task('test_list_remove')
        assert len(task.accepted) == 1

        task = execute_task('list_get')
        assert len(task.entries) == 1

    def test_list_reject(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

        task = execute_task('test_list_reject')
        assert len(task.rejected) == 1

    def test_list_accept_for_real_title(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('test_list_accept_for_real_title')
        assert len(task.accepted) == 1
