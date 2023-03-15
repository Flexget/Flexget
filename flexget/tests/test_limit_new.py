class TestLimitNew:
    config = """
        tasks:
          test:
            mock:
              - {title: 'Item 1'}
              - {title: 'Item 2'}
              - {title: 'Item 3'}
              - {title: 'Item 4'}
            accept_all: yes
            limit_new: 1
    """

    def test_limit_new(self, execute_task):
        task = execute_task('test')
        assert len(task.entries) == 1, 'accepted too many'
        assert task.find_entry('accepted', title='Item 1'), 'accepted wrong item'
        task = execute_task('test')
        assert len(task.entries) == 1, 'accepted too many on second run'
        assert task.find_entry('accepted', title='Item 2'), 'accepted wrong item on second run'
