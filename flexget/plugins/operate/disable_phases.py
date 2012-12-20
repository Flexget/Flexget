from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, task_phases

log = logging.getLogger('disable_phases')


class PluginDisablePhases(object):
    """Disables phases from task execution.

    Mainly meant for advanced users and development.

    Example:

    disable_phases:
      - download
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('list')
        root.accept('choice').accept_choices(task_phases)
        return root

    def on_task_start(self, task, config):
        map(task.disable_phase, config)

register_plugin(PluginDisablePhases, 'disable_phases', api_ver=2)
