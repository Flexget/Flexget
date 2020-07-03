from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='priority')


# TODO: 1.2 figure out replacement for this
# Currently the manager reads this value directly out of the config when the 'execute' command is run, and this plugin
# does nothing but make the config key valid.
# In daemon mode, schedules should be made which run tasks in the proper order instead of using this.
class TaskPriority:
    """Set task priorities"""

    schema = {'type': 'integer'}

    def on_task_start(self, task, config):
        pass


@event('plugin.register')
def register_plugin():
    plugin.register(TaskPriority, 'priority', api_ver=2)
