class TestManipulate:
    config = r"""
        tasks:

          test_1:
            mock:
              - {title: 'abc FOO'}
            manipulate:
              - title:
                  replace:
                    regexp: FOO
                    format: BAR

          test_2:
            mock:
              - {title: '1234 abc'}
            manipulate:
              - title:
                  extract: \d+\s*(.*)

          test_multiple_edits:
            mock:
              - {title: 'abc def'}
            manipulate:
              - title:
                  replace:
                    regexp: abc
                    format: "123"
              - title:
                  extract: \d+\s+(.*)

          test_phase:
            mock:
              - {title: '1234 abc'}
            manipulate:
              - title:
                  phase: metainfo
                  extract: \d+\s*(.*)

          test_remove:
            mock:
              - {title: 'abc', description: 'def'}
            manipulate:
              - description: { remove: yes }

          test_replace_with_group:
            mock:
              - {title: '1234-7890'}
            manipulate:
              - title:
                  replace:
                    regexp: (1234)\-(7890)
                    format: 'e\2'
    """

    def test_replace(self, execute_task):
        task = execute_task('test_1')
        assert task.find_entry('entries', title='abc BAR'), 'replace failed'

    def test_replace_with_group(self, execute_task):
        task = execute_task('test_replace_with_group')
        entry = task.all_entries[0]
        assert entry['title'] == 'e7890', 'Title should have been {} but was {}'.format(
            'e7890',
            entry['title'],
        )

    def test_extract(self, execute_task):
        task = execute_task('test_2')
        assert task.find_entry('entries', title='abc'), 'extract failed'

    def test_multiple_edits(self, execute_task):
        task = execute_task('test_multiple_edits')
        assert task.find_entry('entries', title='def'), 'multiple edits on 1 field failed'

    def test_phase(self, execute_task):
        task = execute_task('test_phase')
        assert task.find_entry('entries', title='abc'), 'extract failed at metainfo phase'

    def test_remove(self, execute_task):
        task = execute_task('test_remove')
        assert 'description' not in task.find_entry('entries', title='abc'), 'remove failed'
