from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='p_priority')


class PluginPriority:
    """
        Allows modifying plugin priorities from default values.

        Example:

        plugin_priority:
          ignore: 50
          series: 100
    """

    schema = {'type': 'object', 'additionalProperties': {'type': 'integer'}}

    def __init__(self):
        self.priorities = {}

    def on_task_start(self, task, config):
        self.priorities = {}
        names = []
        for name, priority in config.items():
            names.append(name)
            originals = self.priorities.setdefault(name, {})
            for phase, phase_event in plugin.plugins[name].phase_handlers.items():
                originals[phase] = phase_event.priority
                logger.debug('stored {} original value {}', phase, phase_event.priority)
                phase_event.priority = priority
                logger.debug('set {} new value {}', phase, priority)
        logger.debug('Changed priority for: {}', ', '.join(names))

    def on_task_exit(self, task, config):
        if not self.priorities:
            logger.debug('nothing changed, aborting restore')
            return
        names = []
        for name in list(config.keys()):
            names.append(name)
            originals = self.priorities[name]
            for phase, priority in originals.items():
                plugin.plugins[name].phase_handlers[phase].priority = priority
        logger.debug('Restored priority for: {}', ', '.join(names))
        self.priorities = {}

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(PluginPriority, 'plugin_priority', api_ver=2)
