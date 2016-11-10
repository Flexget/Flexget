from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('rerun')


class Rerun(object):
    """
    Force a task to rerun for debugging purposes.
    Configured value will set max_rerun value and enables a lock
    that prevents other plugins modifying it.
    """

    schema = {'type': ['integer']}

    def on_task_start(self, task, config):
        log.debug('Setting max_reruns from %s -> %s', task.max_reruns, config)
        task.max_reruns = int(config)
        task.lock_reruns()

    def on_task_input(self, task, config):
        task.rerun()


@event('plugin.register')
def register_plugin():
    plugin.register(Rerun, 'rerun', api_ver=2, debug=True)
