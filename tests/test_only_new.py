class TestOnlyNew:
    config = """
        tasks:
          test:
            mock:
              - {title: 'title 1', url: 'http://localhost/title1'}
            only_new: yes
            disable: [seen] # Disable the seen plugin to make sure only_new does the filtering.
            accept_all: yes
    """

    def test_only_new(self, execute_task, manager):
        task = execute_task('test')
        # only_new will reject the entry on task_exit, make sure accept_all accepted it during filter event though
        assert task.find_entry('rejected', title='title 1', accepted_by='accept_all'), (
            'Test entry missing'
        )
        # run again, should filter
        task = execute_task('test')
        assert task.find_entry('rejected', title='title 1', rejected_by='remember_rejected'), (
            'Seen test entry remains'
        )

        # add another entry to the task
        manager.config['tasks']['test']['mock'].append(
            {'title': 'title 2', 'url': 'http://localhost/title2'}
        )
        # execute again
        task = execute_task('test')
        # both entries should be present as config has changed
        assert task.find_entry('rejected', title='title 1', accepted_by='accept_all'), (
            'title 1 was not found'
        )
        assert task.find_entry('rejected', title='title 2', accepted_by='accept_all'), (
            'title 2 was not found'
        )

        # TODO: Test that new entries are accepted. Tough to do since we can't change the task name or config..
