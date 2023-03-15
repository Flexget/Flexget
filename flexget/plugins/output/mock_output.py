from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='mock_output')


class MockOutput:
    """
    Debugging plugin which records a copy of all accepted entries into a list stored in `mock_output` attribute
    of the task.
    """

    schema = {'type': 'boolean'}

    def on_task_start(self, task, config):
        task.mock_output = []

    def on_task_output(self, task, config):
        task.mock_output.extend(e.copy() for e in task.all_entries if e.accepted)

    def on_task_exit(self, task, config):
        logger.verbose(
            'The following titles were output during this task run: {}',
            ', '.join(e['title'] for e in task.mock_output),
        )


@event('plugin.register')
def register_plugin():
    plugin.register(MockOutput, 'mock_output', debug=True, api_ver=2)
