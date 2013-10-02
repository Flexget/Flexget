from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('rerun')


class MaxReRuns(object):
    """Force a task to rerun for debugging purposes."""

    schema = {'type': 'boolean'}

    def on_task_start(self, task, config):
        if config and not task.is_rerun:
            log.debug('forcing a task rerun')
            task.rerun()


@event('plugin.register')
def register_plugin():
    plugin.register(MaxReRuns, 'rerun', api_ver=2, debug=True)
