from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import validator
from flexget.plugin import register_plugin

log = logging.getLogger('metainfo_task')


class MetainfoTask(object):
    """
    Set 'task' field for entries.
    """

    def validator(self):
        return validator.factory('boolean')

    def on_task_metainfo(self, task, config):
        # check if explicitly disabled (value set to false)
        if config is False:
            return

        for entry in task.entries:
            entry['task'] = task.name


register_plugin(MetainfoTask, 'metainfo_task', api_ver=2, builtin=True)
