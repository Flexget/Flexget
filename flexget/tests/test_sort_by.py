from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest

class TestSortBy(object):
    config = """
        tasks:
          test_title:
            sort_by: title
            mock:
              - {title: 'B C D', url: 'http://localhost/1'}
              - {title: 'A B C', url: 'http://localhost/2'}
              - {title: 'A P E', url: 'http://localhost/3'}
          test_title_reverse:
            sort_by:
              field: title
              reverse: true
            mock:
              - {title: 'B C D', url: 'http://localhost/1'}
              - {title: 'A B C', url: 'http://localhost/2'}
              - {title: 'A P E', url: 'http://localhost/3'}
          test_reverse:
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
          test_ignore_articles:
            sort_by:
              field: title
              ignore_articles: yes
            mock:
              - {title: 'New Series 2', url: 'http://localhost/2'}
              - {title: 'An Owl Looked Back', url: 'http://localhost/4'}
              - {title: 'A New Series', url: 'http://localhost/1'}
              - {title: 'Owl Looked Back Goes to College', url: 'http://localhost/5'}
              - {title: 'The Cat Who Looked Back', url: 'http://localhost/3'}
          test_ignore_articles_custom:
            sort_by:
              field: title
              ignore_articles: '^(the|a)\s'
            mock:
              - {title: 'The Cat Who Looked Back', url: 'http://localhost/3'}
              - {title: 'A New Series', url: 'http://localhost/1'}
              - {title: 'Owl Looked Back Goes to College', url: 'http://localhost/5'}
              - {title: 'New Series 2', url: 'http://localhost/2'}
              - {title: 'An Owl Looked Back', url: 'http://localhost/4'}
    """

    def generate_test_ids(param):
        if param[0:5] == 'test_' or not isinstance(param, list):
            return param
        return '|'

    @pytest.mark.parametrize('task_name,result_titles,fail_reason', [
        ('test_title',
            ['A B C', 'A P E', 'B C D'],
            'Entries should be sorted alphabetically by title'),
        ('test_title_reverse',
            ['B C D', 'A P E', 'A B C'],
            'Entries should be sorted alphabetically by title'),
        ('test_reverse',
            ['A P E', 'A B C', 'B C D'],
            'Entries should be sorted alphabetically by title'),
        ('test_quality',
            ['Test.1080p', 'Test.720p', 'Test.hdtv'],
            'Entries should be sorted by descending quality'),
        ('test_ignore_articles',
            ['The Cat Who Looked Back', 'A New Series', 'New Series 2', 'An Owl Looked Back',
             'Owl Looked Back Goes to College'],
            'Entries should be sorted ignoring articles `a`, `an`, and `the`'),
        ('test_ignore_articles_custom',
            ['An Owl Looked Back', 'The Cat Who Looked Back', 'A New Series', 'New Series 2',
             'Owl Looked Back Goes to College'],
            'Entries should be sorted ignoring articles `a` and `the`')
    ], ids=generate_test_ids)
    def test_sort_by(self, execute_task, task_name, result_titles, fail_reason):
        task = execute_task(task_name)
        for count, title in enumerate(result_titles):
            assert task.entries[count]['title'] == title, fail_reason