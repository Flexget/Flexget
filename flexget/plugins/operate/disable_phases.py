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

    # TODO: schemas are registered to a uri at plugin load, the list of phases may not be complete at that time
    schema = {'type': 'array', 'items': {'type': 'string', 'enum': task_phases}}

    def on_task_start(self, task, config):
        map(task.disable_phase, config)

register_plugin(PluginDisablePhases, 'disable_phases', api_ver=2)
