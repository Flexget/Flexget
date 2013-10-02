from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('priority')


class TaskPriority(object):

    """Set task priorities"""

    def validator(self):
        from flexget import validator
        return validator.factory('integer')

    def on_process_start(self, task, config):
        task.priority = task.config.get('priority', 65535)

@event('plugin.register')
def register_plugin():
    plugin.register(TaskPriority, 'priority', api_ver=2)
