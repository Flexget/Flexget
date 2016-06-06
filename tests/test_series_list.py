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

          test_add_with_attributes:
            mock:
              - {title: 'series 1',
                 url: "http://mock.url/file1.torrent",
                 set: {tvdb_id: "1234", tvmaze_id: "1234", not_valid_id: "1234"},
                 alternate_name: [SER1, SER2],
                 name_regexp: ["^ser", "^series 1$"],
                 qualities: [720p, 1080p],
                 timeframe: '2 days',
                 upgrade: yes,
                 propers: yes,
                 specials: yes,
                 not_a_real_attribute: yes,
                 tracking: 'backfill',
                 identified_by: "ep"}
            accept_all: yes
            list_add:
              - series_list: test_list

    """

    def test_base_series_list(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.accepted) == 1

        task = execute_task('list_get')
        assert len(task.entries) == 1
        assert task.find_entry(title='series 1')

    def test_base_configure_series_with_list(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.accepted) == 1

        task = execute_task('test_basic_configure_series')
        assert len(task.accepted) == 1
        assert task.find_entry(category='accepted', series_name='series 1')

    def test_series_list_with_attributes(self, execute_task):
        task = execute_task('test_add_with_attributes')
        assert len(task.accepted) == 1

        task = execute_task('list_get')
        assert len(task.entries) == 1
        assert task.find_entry(title='series 1')
        assert task.find_entry(set={'tvdb_id': '1234', 'tvmaze_id': '1234'})
        assert task.find_entry(alternate_name=['SER1', 'SER2'])
        assert task.find_entry(name_regexp=["^ser", "^series 1$"])
        assert task.find_entry(qualities=['720p', '1080p'])
        assert task.find_entry(timeframe='2 days')
        assert task.find_entry(upgrade=True)
        assert task.find_entry(propers=True)
        assert task.find_entry(specials=True)
        assert task.find_entry(tracking='backfill')
        assert task.find_entry(identified_by='ep')
        assert not task.find_entry(not_a_real_attribute=True)
