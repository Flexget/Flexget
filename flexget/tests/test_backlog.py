class TestBacklog:
    config = """
        tasks:
          test:
            mock:
              - {title: 'Test.S01E01.hdtv-FlexGet', description: ''}
            set:
              description: '{{description}}I'
              laterfield: 'something'
            # Change the priority of set plugin so it runs on all entries. TODO: Remove, this is an ugly hack.
            plugin_priority:
              set: -254
            backlog: 10 minutes
    """

    def test_backlog(self, manager, execute_task):
        """Tests backlog (and snapshot) functionality."""
        # Test entry comes out as expected on first run
        task = execute_task('test')
        entry = task.find_entry(title='Test.S01E01.hdtv-FlexGet')
        assert entry['description'] == 'I'
        assert entry['laterfield'] == 'something'
        # Simulate entry leaving the task, make sure backlog injects it
        del manager.config['tasks']['test']['mock']
        task = execute_task('test')
        entry = task.find_entry(title='Test.S01E01.hdtv-FlexGet')
        assert entry['description'] == 'I'
        assert entry['laterfield'] == 'something'
        # This time take away the set plugin too, to make sure data is being restored at it's state from input
        del manager.config['tasks']['test']['set']
        task = execute_task('test')
        entry = task.find_entry(title='Test.S01E01.hdtv-FlexGet')
        assert entry['description'] == ''
        assert 'laterfield' not in entry
