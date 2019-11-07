from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin


class TestSubtask(object):
    config = """
        tasks:
          subtask:
            mock:
            - title: subtask entry 1
              other_field: 5
            - title: subtask entry 1
            accept_all: yes
          main_task:
            subtask: subtask
    """

    def test_subtask(self, manager, execute_task):
        task = execute_task('main_task')
        assert len(task.entries) == 2, 'Should have produced both subtask entries'
        assert len(task.accepted) == 0, 'Accepted status should not pass through from subtask'
        assert task.find_entry(title='subtask entry 1')['other_field'] == 5, 'other fields should pass through'
