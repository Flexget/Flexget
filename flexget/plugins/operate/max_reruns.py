from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.task import Task

logger = logger.bind(name='max_reruns')


class MaxReRuns:
    """Overrides the maximum amount of re-runs allowed by a task."""

    schema = {'type': 'integer'}

    def __init__(self):
        self.default = Task.RERUN_DEFAULT

    def reset(self, task):
        task.unlock_reruns()
        task.max_reruns = self.default
        logger.debug('changing max task rerun variable back to: {}', self.default)

    def on_task_start(self, task, config):
        self.default = task.max_reruns
        logger.debug('saving old max task rerun value: {}', self.default)
        task.max_reruns = int(config)
        task.lock_reruns()
        logger.debug('changing max task rerun variable to: {}', config)

    def on_task_exit(self, task, config):
        if task.rerun_count > task.max_reruns:
            self.reset(task)

    def on_task_abort(self, task, config):
        self.reset(task)


@event('plugin.register')
def register_plugin():
    plugin.register(MaxReRuns, 'max_reruns', api_ver=2)
