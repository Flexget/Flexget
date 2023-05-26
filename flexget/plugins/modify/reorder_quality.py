from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils import qualities

logger = logger.bind(name='reorder_quality')


class ReorderQuality:
    """
    Allows modifying quality priorities from default ordering.

    Example:

    reorder_quality:
      webrip:
        above: hdtv
    """

    schema = {
        'type': 'object',
        'additionalProperties': {
            'type': 'object',
            'properties': {
                'above': {'type': 'string', 'format': 'quality'},
                'below': {'type': 'string', 'format': 'quality'},
            },
            'maxProperties': 1,
        },
    }

    def __init__(self):
        self.quality_priorities = {}

    def on_task_start(self, task, config):
        self.quality_priorities = {}
        for quality, _config in config.items():
            action, other_quality = list(_config.items())[0]

            if quality not in qualities._registry:
                raise plugin.PluginError('%s is not a valid quality' % quality)

            quality_component = qualities._registry[quality]
            other_quality_component = qualities._registry[other_quality]

            if quality_component.type != other_quality_component.type:
                raise plugin.PluginError(
                    '{}={} and {}={} do not have the same quality type'.format(
                        quality,
                        quality_component.type,
                        other_quality,
                        other_quality_component.type,
                    )
                )

            self.quality_priorities[quality] = quality_component.value
            logger.debug('stored {} original value {}', quality, quality_component.value)

            new_value = other_quality_component.value
            if action == 'above':
                new_value += 1
            else:
                new_value -= 1

            quality_component.value = new_value
            logger.debug('New value for {}: {} ({} {})', quality, new_value, action, other_quality)
        logger.debug('Changed priority for: {}', ', '.join(list(config.keys())))

    def on_task_exit(self, task, config):
        if not self.quality_priorities:
            logger.debug('nothing changed, aborting restore')
            return
        for name, value in self.quality_priorities.items():
            qualities._registry[name].value = value
        logger.debug('Restored priority for: {}', ', '.join(list(self.quality_priorities.keys())))
        self.quality_priorities = {}

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(ReorderQuality, 'reorder_quality', api_ver=2)
