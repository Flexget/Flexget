from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin


class TestSeriesList(object):
    config = """
        templates:
          global:
            disable: [seen]

        tasks:
          list_get:
            series_list: test_list

          test_list_add:
            mock:
              - {title: 'series 1', url: "http://mock.url/file1.torrent"}
            accept_all: yes
            list_add:
              - series_list: test_list

          test_basic_configure_series:
            mock:
              - {title: 'series 1.s01e01.720p.HDTV-flexget', url: "http://mock.url/file1.torrent"}
            configure_series:
              from:
                series_list: test_list

    """

    def test_base_series_list(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 1

        task = execute_task('list_get')
        assert len(task.entries) == 1
        assert task.find_entry(title='series 1')

    def test_base_configure_series_with_list(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 1

        task = execute_task('test_basic_configure_series')
        assert len(task.entries) == 1
        assert task.find_entry(series_name='series 1')


