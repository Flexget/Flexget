from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget.manager import Session
from flexget.plugins.filter.pending_approval import PendingEntry


class TestPendingApproval(object):
    config = """
        tasks:
          test:
            mock:
              - {title: 'title 1', url: 'http://localhost/title1', other_attribute: 'bla'}
            pending_approval: yes
    """

    def test_pending_approval(self, execute_task, manager):
        task = execute_task('test')
        assert len(task.entries) == 0
        assert len(task.accepted) == 0

        # Mark entry as approved, this will be done by CLI/API
        with Session() as session:
            pnd_entry = session.query(PendingEntry).first()
            pnd_entry.approved = True

        task = execute_task('test')
        assert len(task.entries) == 1
        assert len(task.accepted) == 1

        assert task.find_entry(other_attribute='bla')

        task = execute_task('test')
        assert len(task.entries) == 0
        assert len(task.accepted) == 0
