from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestOnlyNew(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'title 1', url: 'http://localhost/title1'}
            only_new: yes
            disable_builtins: [seen] # Disable the seen plugin to make sure only_new does the filtering.
            accept_all: yes
            mock_output: yes
    """

    def test_only_new(self):
        self.execute_task('test')
        entry = self.task.find_entry('rejected', title='title 1')
        assert entry, 'Test entry missing'
        # only_new will reject the entry on task_exit, make sure accept_all accepted it during filter event though
        assert entry in self.task.mock_output
        # run again, should filter
        self.execute_task('test')
        entry = self.task.find_entry('rejected', title='title 1', rejected_by='remember_rejected')
        assert entry
        assert entry not in self.task.mock_output

        # add another entry to the task
        self.manager.config['tasks']['test']['mock'].append({'title': 'title 2', 'url': 'http://localhost/title2'})
        # execute again
        self.execute_task('test')
        # both entries should be present as config has changed
        entry = self.task.find_entry('rejected', title='title 1')
        assert entry, 'title 1 was not found'
        assert entry in self.task.mock_output
        assert self.task.find_entry('rejected', title='title 2')
        assert entry, 'title 2 was not found'
        assert entry in self.task.mock_output

        # TODO: Test that new entries are accepted. Tough to do since we can't change the task name or config..
