from flexget import plugin
from flexget.entry import Entry


class OneEntryInput:
    """Fake input plugin, fails if second entry is grabbed."""

    def on_task_input(self, task, config):
        yield Entry(title='Test', url='http://test.com')
        raise RuntimeError('Should not have tried to get second entry.')


plugin.register(OneEntryInput, 'one_entry_input', api_ver=2)


class TestLimit:
    config = """
        tasks:
          test_limit:
            limit:
              amount: 2
              from:
                mock:
                - title: Entry 1
                - title: Entry 2
                - title: Entry 3
          test_limit_generator:
            limit:
              amount: 1
              from:
                one_entry_input: yes
    """

    def test_limit(self, execute_task):
        task = execute_task('test_limit')
        assert len(task.all_entries) == 2

    def test_limit_generator(self, execute_task):
        task = execute_task('test_limit_generator')
        assert len(task.all_entries) == 1
