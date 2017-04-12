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

    def on_task_start(self, task, config):
        for item in config:
            for plugin_name, plugin_config in item.items():
                try:
                    thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                except AttributeError:
                    raise PluginError('Plugin %s does not support list interface' % plugin_name)
                if thelist.immutable:
                    raise plugin.PluginError(thelist.immutable)

    # Run later in the phase, to capture any entry fields that might change during the output phase
    @plugin.priority(0)
    def on_task_output(self, task, config):
        if not len(task.accepted) > 0:
            log.debug('no accepted entries, nothing to add')
            return

        for item in config:
            for plugin_name, plugin_config in item.items():
                thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                if task.manager.options.test and thelist.online:
                    log.info('`%s` is marked as an online plugin, would add accepted items outside of --test mode. '
                             'Skipping', plugin_name)
                    continue
                log.verbose('adding accepted entries into %s - %s', plugin_name, plugin_config)
                thelist |= task.accepted


@event('plugin.register')
def register_plugin():
    plugin.register(ListAdd, 'list_add', api_ver=2)
