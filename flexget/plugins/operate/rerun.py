from __future__ import unicode_literals, division, absolute_import
import logging
from flexget import validator
from flexget.plugin import register_plugin

log = logging.getLogger('rerun')


class MaxReRuns(object):
    """Force a task to rerun for debugging purposes."""

    def validator(self):
        root = validator.factory('boolean')
        return root

    def on_task_start(self, task, config):
        if config and not task.is_rerun:
            log.debug('forcing a task rerun')
            task.rerun()


register_plugin(MaxReRuns, 'rerun', api_ver=2, debug=True)
