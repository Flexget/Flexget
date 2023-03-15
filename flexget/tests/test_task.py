class TestTemplate:
    config = """
        templates:
          test_series:
            series:
              test:
                - House
              settings:
                test:
                  identified_by: ep

        tasks:
          test:
            template: test_series
            next_series_episodes:
              from_start: yes
            rerun: 0
    """

    def test_config_template_hash_check(self, manager, execute_task):
        task = execute_task('test')
        assert len(task.entries) == 1, 'Should have emitted House S01E01'

        manager.config['templates']['test_series']['series']['test'].append('Hawaii Five-O')

        task = execute_task('test')
        assert len(task.entries) == 2, 'Should have emitted House S01E02 and Hawaii Five-O S01E01'
