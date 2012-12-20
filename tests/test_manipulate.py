from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestManipulate(FlexGetBase):

    __yaml__ = """
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
    """

    def test_replace(self):
        self.execute_task('test_1')
        assert self.task.find_entry('entries', title='abc BAR'), 'replace failed'

    def test_extract(self):
        self.execute_task('test_2')
        assert self.task.find_entry('entries', title='abc'), 'extract failed'

    def test_multiple_edits(self):
        self.execute_task('test_multiple_edits')
        assert self.task.find_entry('entries', title='def'), 'multiple edits on 1 field failed'

    def test_phase(self):
        self.execute_task('test_phase')
        assert self.task.find_entry('entries', title='abc'), 'extract failed at metainfo phase'

    def test_remove(self):
        self.execute_task('test_remove')
        assert 'description' not in self.task.find_entry('entries', title='abc'), 'remove failed'
