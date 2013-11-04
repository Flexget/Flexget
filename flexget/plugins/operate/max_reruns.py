from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.task import Task

log = logging.getLogger('max_reruns')


class MaxReRuns(object):
    """Overrides the maximum amount of re-runs allowed by a task."""

    schema = {'type': 'integer'}

    def __init__(self):
        self.default = Task.max_reruns

    def on_task_start(self, task, config):
        self.default = task.max_reruns
        task.max_reruns = int(config)
        log.debug('changing max task rerun variable to: %s' % config)

    def on_task_exit(self, task, config):
        log.debug('restoring max task rerun variable to: %s' % self.default)
        task.max_reruns = self.default

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(MaxReRuns, 'max_reruns', api_ver=2)
