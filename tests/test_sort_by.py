from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestSortBy(FlexGetBase):

    __yaml__ = """
        tasks:
          test1:
            sort_by: title
            mock:
              - {title: 'B C D', url: 'http://localhost/1'}
              - {title: 'A B C', url: 'http://localhost/2'}
              - {title: 'A P E', url: 'http://localhost/3'}
          test2:
            sort_by:
              field: title
              reverse: true
            mock:
              - {title: 'B C D', url: 'http://localhost/1'}
              - {title: 'A B C', url: 'http://localhost/2'}
              - {title: 'A P E', url: 'http://localhost/3'}
          test3:
            sort_by:
                reverse: true
            mock:
              - {title: 'B C D', url: 'http://localhost/1'}
              - {title: 'A B C', url: 'http://localhost/2'}
              - {title: 'A P E', url: 'http://localhost/3'}
          test_quality:
            sort_by:
              field: quality
              reverse: true
            mock:
              - {title: 'Test.720p'}
              - {title: 'Test.hdtv'}
              - {title: 'Test.1080p'}

    """

    def test_sort_by_title(self):
        self.execute_task('test1')
        assert self.task.entries[0]['title'] == 'A B C', 'Entries sorted alphabetically by title'
        assert self.task.entries[1]['title'] == 'A P E', 'Entries sorted alphabetically by title'
        assert self.task.entries[2]['title'] == 'B C D', 'Entries sorted alphabetically by title'

    def test_sort_by_title_reverse(self):
        self.execute_task('test2')
        assert self.task.entries[0]['title'] == 'B C D', 'Entries sorted alphabetically by title'
        assert self.task.entries[1]['title'] == 'A P E', 'Entries sorted alphabetically by title'
        assert self.task.entries[2]['title'] == 'A B C', 'Entries sorted alphabetically by title'

    def test_sort_by_reverse(self):
        self.execute_task('test3')
        assert self.task.entries[0]['title'] == 'A P E', 'Entries sorted alphabetically by title'
        assert self.task.entries[1]['title'] == 'A B C', 'Entries sorted alphabetically by title'
        assert self.task.entries[2]['title'] == 'B C D', 'Entries sorted alphabetically by title'

    def test_quality_sort(self):
        self.execute_task('test_quality')
        assert self.task.entries[0]['title'] == 'Test.1080p', 'Entries should be sorted by descending quality'
        assert self.task.entries[1]['title'] == 'Test.720p', 'Entries should be sorted by descending quality'
        assert self.task.entries[2]['title'] == 'Test.hdtv', 'Entries should be sorted by descending quality'
