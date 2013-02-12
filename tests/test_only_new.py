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
    """

    def test_only_new(self):
        self.execute_task('test')
        # only_new will reject the entry on task_exit, make sure accept_all accepted it during filter event though
        assert self.task.find_entry('rejected', title='title 1', accepted_by='accept_all'), 'Test entry missing'
        # run again, should filter
        self.execute_task('test')
        assert self.task.find_entry('rejected', title='title 1', rejected_by='remember_rejected'), 'Seen test entry remains'

        # add another entry to the task
        self.manager.config['tasks']['test']['mock'].append({'title': 'title 2', 'url': 'http://localhost/title2'})
        # execute again
        self.execute_task('test')
        # both entries should be present as config has changed
        assert self.task.find_entry('rejected', title='title 1', accepted_by='accept_all'), 'title 1 was not found'
        assert self.task.find_entry('rejected', title='title 2', accepted_by='accept_all'), 'title 2 was not found'

        # TODO: Test that new entries are accepted. Tough to do since we can't change the task name or config..
