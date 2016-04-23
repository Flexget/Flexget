from __future__ import unicode_literals, division, absolute_import
from builtins import *


class TestListInterface(object):
    config = """
        templates:
          global:
            disable: [seen]

        tasks:
          list_get:
            movie_list: test_list

          list_1_get:
            movie_list: list 1

          list_2_get:
            movie_list: list 2

          test_list_add:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
            accept_all: yes
            list_add:
              - movie_list: test_list

          list_1_add:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
            accept_all: yes
            list_add:
              - movie_list: list 1

          list_2_add:
            mock:
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            accept_all: yes
            list_add:
              - movie_list: list 2

          test_multiple_list_add:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
            accept_all: yes
            list_add:
              - movie_list: list 1
              - movie_list: list 2

          test_list_accept_with_remove:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_accept:
              - movie_list: test_list

          test_list_accept_without_remove:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_accept:
              lists:
                - movie_list: test_list
              remove_on_accept: no

          test_multiple_list_accept_with_remove:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_accept:
              - movie_list: list 1
              - movie_list: list 2

          test_multiple_list_accept_without_remove:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_accept:
              lists:
                - movie_list: list 1
                - movie_list: list 2
              remove_on_accept: no

          test_list_remove:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
            accept_all: yes
            list_remove:
              - movie_list: test_list

          test_list_reject:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_reject:
              - movie_list: test_list

          test_allowed_identifiers:
            mock:
              - {title: 'title 1',
                 url: "http://mock.url/file1.torrent",
                 imdb_id: "tt1234567",
                 trakt_movie_id: "12345",
                 tmdb_id: "3456",
                 fake_id_name: "123abc"
                 }
            accept_all: yes
            list_add:
              - movie_list: test_list
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

        assert task.find_entry(imdb_id='tt1234567')
        assert task.find_entry(trakt_movie_id='12345')
        assert task.find_entry(tmdb_id='3456')
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
