from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('disable_phases')


class PluginDisablePhases(object):
    """Disables phases from task execution.

    Mainly meant for advanced users and development.

    Example:

    disable_phases:
      - download
    """

    @property
    def schema(self):
        return {'type': 'array', 'items': {'type': 'string', 'enum': plugin.task_phases}}

    def on_task_start(self, task, config):
        list(map(task.disable_phase, config))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginDisablePhases, 'disable_phases', api_ver=2)
