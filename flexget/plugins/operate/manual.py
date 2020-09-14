from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='manual')


class ManualTask:
    """Only execute task when specified with --tasks"""

    schema = {'type': 'boolean'}

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_start(self, task, config):
        # Make sure we need to run
        if not config:
            return
        # If --task hasn't been specified disable this plugin
        # TODO: allow_manual is confusing. Make it less confusing.
        if (
            not task.options.tasks
            or task.name not in task.options.tasks
            or not task.options.allow_manual
        ):
            logger.debug(
                'Disabling task {}, task can only run in manual mode (via API/CLI)', task.name
            )
            task.abort('manual task not specified in --tasks', silent=True)


@event('plugin.register')
def register_plugin():
    plugin.register(ManualTask, 'manual', api_ver=2)
