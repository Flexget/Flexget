from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError

log = logging.getLogger('list_clear')


class ListClear(object):
    schema = {
        'type': 'object',
        'properties': {
            'what': {'type': 'array', 'items':
                {'allOf': [
                    {'$ref': '/schema/plugins?interface=list'},
                    {'maxProperties': 1,
                     'error_maxProperties': 'Plugin options within list_clear plugin must be indented '
                                            '2 more spaces than the first letter of the plugin name.',
                     'minProperties': 1}]}},
            'phase': {'type': 'string', 'enum': plugin.task_phases, 'default': 'start'}
        },
        'required': ['what']
    }

    def __getattr__(self, phase):
        # enable plugin in regular task phases
        if phase.replace('on_task_', '') in plugin.task_phases:
            return self.clear

    @plugin.priority(255)
    def clear(self, task, config):
        for item in config['what']:
            for plugin_name, plugin_config in item.items():
                try:
                    thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                except AttributeError:
                    raise PluginError('Plugin %s does not support list interface' % plugin_name)
                if thelist.immutable:
                    raise plugin.PluginError(thelist.immutable)
                if config['phase'] == task.current_phase:
                    if task.manager.options.test and thelist.online:
                        log.info('would have cleared all items from %s - %s', plugin_name, plugin_config)
                        continue
                    log.verbose('clearing all items from %s - %s', plugin_name, plugin_config)
                    thelist.clear()


@event('plugin.register')
def register_plugin():
    plugin.register(ListClear, 'list_clear', api_ver=2)
