import pytest


class TestSortBy:
    config = r"""
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
          test_multi_field:
            sort_by:
            - field: number1
            - field: number2
            mock:
            - title: A
              number1: 10
              number2: 2
            - title: B
              number1: 1
              number2: 15
            - title: C
              number1: 10
              number2: 1
          test_missing_field:
            sort_by: maybe_field
            mock:
            - title: A
              maybe_field: 1
            - title: B
            - title: C
              maybe_field: 2
          test_missing_field_reverse:
            sort_by:
              field: maybe_field
              reverse: yes
            mock:
            - title: A
              maybe_field: 1
            - title: B
            - title: C
              maybe_field: 2
          test_jinja_field:
            sort_by: "dict_field.b"
            mock:
            - title: A
              dict_field: {a: 0, b: 2}
            - title: B
              dict_field: {a: 1, b: 1}
            - title: C
              dict_field: {a: 2, b: 0}
    """

    def generate_test_ids(param):
        if param[0:5] == 'test_' or not isinstance(param, list):
            return param
        return '|'

    @pytest.mark.parametrize(
        'task_name,result_titles,fail_reason',
        [
            (
                'test_title',
                ['A B C', 'A P E', 'B C D'],
                'Entries should be sorted alphabetically by title',
            ),
            (
                'test_title_reverse',
                ['B C D', 'A P E', 'A B C'],
                'Entries should be sorted alphabetically by title',
            ),
            (
                'test_reverse',
                ['A P E', 'A B C', 'B C D'],
                'Entries should be sorted alphabetically by title',
            ),
            (
                'test_quality',
                ['Test.1080p', 'Test.720p', 'Test.hdtv'],
                'Entries should be sorted by descending quality',
            ),
            (
                'test_ignore_articles',
                [
                    'The Cat Who Looked Back',
                    'A New Series',
                    'New Series 2',
                    'An Owl Looked Back',
                    'Owl Looked Back Goes to College',
                ],
                'Entries should be sorted ignoring articles `a`, `an`, and `the`',
            ),
            (
                'test_ignore_articles_custom',
                [
                    'An Owl Looked Back',
                    'The Cat Who Looked Back',
                    'A New Series',
                    'New Series 2',
                    'Owl Looked Back Goes to College',
                ],
                'Entries should be sorted ignoring articles `a` and `the`',
            ),
            (
                'test_multi_field',
                ['B', 'C', 'A'],
                'Entries should be sorted by both fields, ascending',
            ),
            ('test_missing_field', ['A', 'C', 'B'], 'Entries without field should be sorted last'),
            (
                'test_missing_field_reverse',
                ['C', 'A', 'B'],
                'Entries without field should be sorted last',
            ),
            ('test_jinja_field', ['C', 'B', 'A'], 'Entries without field should be sorted last'),
        ],
        ids=generate_test_ids,
    )
    def test_sort_by(self, execute_task, task_name, result_titles, fail_reason):
        task = execute_task(task_name)
        for count, title in enumerate(result_titles):
            assert task.entries[count]['title'] == title, fail_reason
