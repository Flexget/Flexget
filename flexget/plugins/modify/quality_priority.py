from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils import qualities

log = logging.getLogger('quality_priority')


class QualityPriority(object):
    """
        Allows modifying quality priorities from default values.

        Example:

        quality_priority:
          webrip: 155  # just above hdtv
    """

    schema = {'type': 'object', 'additionalProperties': {'type': 'integer'}}

    def __init__(self):
        self.quality_priorities = {}

    def on_task_start(self, task, config):
        self.quality_priorities = {}
        names = []
        for name, value in config.items():
            quality_component = qualities._registry[name]
            self.quality_priorities[name] = quality_component.value
            log.debug('stored %s original value %s' % (name, quality_component.value))
            quality_component.value = value
            log.debug('set %s new value %s' % (name, value))
        log.debug('Changed priority for: %s' % ', '.join(names))

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
    plugin.register(QualityPriority, 'quality_priority', api_ver=2)
