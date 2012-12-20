from __future__ import unicode_literals, division, absolute_import
import logging
from flexget import plugin, validator

log = logging.getLogger('metainfo_task')


class MetainfoTask(plugin.BuiltinPlugin):
    """
    Utility:

    Set task attribute for entries.
    """

    def validator(self):
        return validator.factory('boolean')

    def on_task_metainfo(self, task, config):
        # check if explicitely disabled (value set to false)
        if config is False:
            return

        for entry in task.entries:
            entry['task'] = task.name
