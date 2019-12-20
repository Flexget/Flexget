from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='rerun')


class Rerun:
    """
    Force a task to rerun for debugging purposes.
    Configured value will set max_rerun value and enables a lock
    that prevents other plugins modifying it.
    """

    schema = {'type': ['integer']}

    def on_task_start(self, task, config):
        logger.debug('Setting max_reruns from {} -> {}', task.max_reruns, config)
        task.max_reruns = int(config)
        task.lock_reruns()

    def on_task_input(self, task, config):
        task.rerun()


@event('plugin.register')
def register_plugin():
    plugin.register(Rerun, 'rerun', api_ver=2, debug=True)
