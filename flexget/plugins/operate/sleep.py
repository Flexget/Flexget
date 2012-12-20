from __future__ import unicode_literals, division, absolute_import
import logging
import time
from flexget.plugin import register_plugin, priority

log = logging.getLogger('sleep')


class PluginSleep(object):
    """Causes a pause to occur before execution of a task"""

    def validator(self):
        from flexget import validator
        return validator.factory('number')

    @priority(255)
    def on_task_start(self, task, config):
        if config:
            log.verbose('Sleeping for %d seconds.' % config)
            time.sleep(config)

register_plugin(PluginSleep, 'sleep', api_ver=2)
