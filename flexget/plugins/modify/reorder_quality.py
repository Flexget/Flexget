from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils import qualities

log = logging.getLogger('reorder_quality')


class ReorderQuality(object):
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
                'below': {'type': 'string', 'format': 'quality'}
            },
            'maxProperties': 1
        }
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
                raise plugin.PluginError('%s=%s and %s=%s do not have the same quality type' %
                                         (quality, quality_component.type, other_quality, other_quality_component.type))

            self.quality_priorities[quality] = quality_component.value
            log.debug('stored %s original value %s' % (quality, quality_component.value))

            new_value = other_quality_component.value
            if action == 'above':
                new_value += 1
            else:
                new_value -= 1

            quality_component.value = new_value
            log.debug('New value for %s: %s (%s %s)', quality, new_value, action, other_quality)
        log.debug('Changed priority for: %s' % ', '.join(list(config.keys())))

    def on_task_exit(self, task, config):
        if not self.quality_priorities:
            log.debug('nothing changed, aborting restore')
            return
        for name, value in self.quality_priorities.items():
            qualities._registry[name].value = value
        log.debug('Restored priority for: %s' % ', '.join(list(self.quality_priorities.keys())))
        self.quality_priorities = {}

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(ReorderQuality, 'reorder_quality', api_ver=2)
