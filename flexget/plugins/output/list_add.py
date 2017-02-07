from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError

log = logging.getLogger('list_add')


class ListAdd(object):
    schema = {
        'type': 'array',
        'items': {
            'allOf': [
                {'$ref': '/schema/plugins?interface=list'},
                {
                    'maxProperties': 1,
                    'error_maxProperties': 'Plugin options within list_add plugin must be indented 2 more spaces than '
                                           'the first letter of the plugin name.',
                    'minProperties': 1
                }
            ]
        }
    }

    # Run later in the phase, to capture any entry fields that might change during the output phase
    @plugin.priority(0)
    def on_task_output(self, task, config):
        if not task.accepted:
            log.debug('no accepted entries, nothing to add')
            return

        for item in config:
            for plugin_name, plugin_config in item.items():
                try:
                    framework = plugin.get_plugin_by_name('list_framework').instance
                    list_manager = framework.ListManager(plugin_name, plugin_config)
                except PluginError as e:
                    log.error(e.value)
                    continue
                if task.manager.options.test and list_manager.list.online:
                    log.info('`%s` is marked as an online plugin, would add accepted items outside of --test mode. '
                             'Skipping', plugin_name)
                    continue
                list_manager.add(task.accepted)


@event('plugin.register')
def register_plugin():
    plugin.register(ListAdd, 'list_add', api_ver=2)
