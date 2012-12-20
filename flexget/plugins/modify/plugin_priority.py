from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import plugins, register_plugin

log = logging.getLogger('p_priority')


class PluginPriority(object):

    """
        Allows modifying plugin priorities from default values.

        Example:

        plugin_priority:
          ignore: 50
          series: 100
    """

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept_any_key('integer')
        return config

    def __init__(self):
        self.priorities = {}

    def on_task_start(self, task):
        self.priorities = {}
        names = []
        for name, priority in task.config.get('plugin_priority', {}).iteritems():
            names.append(name)
            originals = self.priorities.setdefault(name, {})
            for phase, event in plugins[name].phase_handlers.iteritems():
                originals[phase] = event.priority
                log.debug('stored %s original value %s' % (phase, event.priority))
                event.priority = priority
                log.debug('set %s new value %s' % (phase, priority))
        log.debug('Changed priority for: %s' % ', '.join(names))

    def on_task_exit(self, task):
        if not self.priorities:
            log.debug('nothing changed, aborting restore')
            return
        names = []
        for name in task.config.get('plugin_priority', {}).keys():
            names.append(name)
            originals = self.priorities[name]
            for phase, priority in originals.iteritems():
                plugins[name].phase_handlers[phase].priority = priority
        log.debug('Restored priority for: %s' % ', '.join(names))
        self.priorities = {}

    on_task_abort = on_task_exit

register_plugin(PluginPriority, 'plugin_priority')
