from __future__ import unicode_literals, division, absolute_import
import logging
from flexget import validator
from flexget.task import Task
from flexget.plugin import register_plugin

log = logging.getLogger('max_reruns')


class MaxReRuns(object):
    """Overrides the maximum amount of re-runs allowed by a task."""

    def __init__(self):
        self.default = Task.max_reruns

    def validator(self):
        root = validator.factory('integer')
        return root

    def on_task_start(self, task, config):
        self.default = task.max_reruns
        task.max_reruns = config
        log.debug('changing max task rerun variable to: %s' % config)

    def on_task_exit(self, task, config):
        log.debug('restoring max task rerun variable to: %s' % self.default)
        task.max_reruns = self.default

    on_task_abort = on_task_exit


register_plugin(MaxReRuns, 'max_reruns', api_ver=2)
