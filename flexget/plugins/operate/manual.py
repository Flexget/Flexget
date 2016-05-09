from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('manual')


class ManualTask(object):
    """Only execute task when specified with --tasks"""

    schema = {'type': 'boolean'}

    @plugin.priority(255)
    def on_task_start(self, task, config):
        # Make sure we need to run
        if not config:
            return
        # If --task hasn't been specified disable this plugin
        if not task.options.tasks or task.name not in task.options.tasks:
            log.debug('Disabling task %s' % task.name)
            task.abort('manual task not specified in --tasks', silent=True)


@event('plugin.register')
def register_plugin():
    plugin.register(ManualTask, 'manual', api_ver=2)
