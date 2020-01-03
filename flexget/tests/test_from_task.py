class TestFromTask(object):
    config = """
        tasks:
          subtask:
            mock:
            - title: subtask entry 1
              other_field: 5
            - title: subtask entry 1
            accept_all: yes
          main_task:
            from_task: subtask
    """

    def test_from_task(self, execute_task):
        task = execute_task('main_task')
        assert len(task.entries) == 2, 'Should have produced both subtask entries'
        assert len(task.accepted) == 0, 'Accepted status should not pass through from subtask'
        assert (
            task.find_entry(title='subtask entry 1')['other_field'] == 5
        ), 'other fields should pass through'
        task = execute_task('main_task')
        assert len(task.entries) == 2, "seen plugin shouldn't reject subtask entries"
