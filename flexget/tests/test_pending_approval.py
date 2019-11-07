from flexget.components.pending_approval.db import PendingEntry
from flexget.manager import Session


class TestPendingApproval:
    config = """
        tasks:
          test:
            mock:
              - {title: 'title 1', url: 'http://localhost/title1', other_attribute: 'bla'}
            pending_approval: yes
    """

    def test_pending_approval(self, execute_task, manager):
        task = execute_task('test')
        assert len(task.all_entries) == 1
        assert len(task.rejected) == 1
        assert len(task.accepted) == 0

        # Mark entry as approved, this will be done by CLI/API
        with Session() as session:
            pnd_entry = session.query(PendingEntry).first()
            pnd_entry.approved = True

        task = execute_task('test')
        assert len(task.all_entries) == 2
        assert len(task.rejected) == 0
        assert len(task.accepted) == 1

        assert task.find_entry(other_attribute='bla')

        task = execute_task('test')
        assert len(task.all_entries) == 1
        assert len(task.rejected) == 1
        assert len(task.accepted) == 0
