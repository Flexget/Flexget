from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError

log = logging.getLogger('list_match')


class ListMatch(object):
    schema = {
        'type': 'object',
        'properties': {
            'from': {'type': 'array',
                     'items':
                         {'allOf': [
                             {'$ref': '/schema/plugins?group=list'},
                             {
                                 'maxProperties': 1,
                                 'error_maxProperties': 'Plugin options within list_match plugin must be indented '
                                                        '2 more spaces than the first letter of the plugin name.',
                                 'minProperties': 1
                             }
                         ]
                         }
                     },
            'action': {'type': 'string', 'enum': ['accept', 'reject'], 'default': 'accept'},
            'remove_on_match': {'type': 'boolean', 'default': True},
            'single_match': {'type': 'boolean', 'default': True},
        }
    }

    def on_task_filter(self, task, config):
        for item in config['from']:
            for plugin_name, plugin_config in item.items():
                try:
                    thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                except AttributeError:
                    raise PluginError('Plugin %s does not support list interface' % plugin_name)
                cached_items = []
                for entry in task.entries:
                    result = thelist.get(entry)
                    if result:
                        if config['action'] == 'accept':
                            if config['single_match'] and result not in cached_items:
                                cached_items.append(result)
                            entry.accept()
                        elif config['action'] == 'reject':
                            entry.reject()

    def on_task_learn(self, task, config):
        if not config['remove_on_match']:
            return
        for item in config['from']:
            for plugin_name, plugin_config in item.items():
                try:
                    thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                except AttributeError:
                    raise PluginError('Plugin %s does not support list interface' % plugin_name)
                if task.manager.options.test and thelist.online:
                    log.info('`%s` is marked as online, would remove accepted items outside of --test mode.',
                             plugin_name)
                    continue
                log.verbose('removing accepted entries from %s - %s', plugin_name, plugin_config)
                thelist -= task.accepted


@event('plugin.register')
def register_plugin():
    plugin.register(ListMatch, 'list_match', api_ver=2)
