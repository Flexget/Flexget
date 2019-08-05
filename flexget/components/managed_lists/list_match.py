from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError

log = logging.getLogger('list_match')


class ListMatch(object):
    schema = {
        'type': 'object',
        'properties': {
            'from': {
                'type': 'array',
                'items': {
                    'allOf': [
                        {'$ref': '/schema/plugins?interface=list'},
                        {
                            'maxProperties': 1,
                            'error_maxProperties': 'Plugin options within list_match plugin must be indented '
                            '2 more spaces than the first letter of the plugin name.',
                            'minProperties': 1,
                        },
                    ]
                },
            },
            'action': {'type': 'string', 'enum': ['accept', 'reject'], 'default': 'accept'},
            'remove_on_match': {'type': 'boolean', 'default': True},
            'single_match': {'type': 'boolean', 'default': True},
        },
        'additionalProperties': False,
    }

    @plugin.priority(0)
    def on_task_filter(self, task, config):
        for item in config['from']:
            for plugin_name, plugin_config in item.items():
                try:
                    thelist = plugin.get(plugin_name, self).get_list(plugin_config)
                except AttributeError:
                    raise PluginError('Plugin %s does not support list interface' % plugin_name)
                already_accepted = []
                for entry in task.entries:
                    result = thelist.get(entry)
                    if not result:
                        continue
                    if config['action'] == 'accept':
                        if config['single_match']:
                            if result not in already_accepted:
                                already_accepted.append(result)
                                # Add all new result data to entry
                                for key in result:
                                    if key not in entry:
                                        entry[key] = result[key]
                                entry.accept()
                        else:
                            entry.accept()
                    elif config['action'] == 'reject':
                        entry.reject()

    def on_task_learn(self, task, config):
        if not config['remove_on_match'] or not len(task.accepted) > 0:
            return
        for item in config['from']:
            for plugin_name, plugin_config in item.items():
                try:
                    thelist = plugin.get(plugin_name, self).get_list(plugin_config)
                except AttributeError:
                    raise PluginError('Plugin %s does not support list interface' % plugin_name)
                if task.manager.options.test and thelist.online:
                    log.info(
                        '`%s` is marked as online, would remove accepted items outside of --test mode.',
                        plugin_name,
                    )
                    continue
                log.verbose('removing accepted entries from %s - %s', plugin_name, plugin_config)
                thelist -= task.accepted


@event('plugin.register')
def register_plugin():
    plugin.register(ListMatch, 'list_match', api_ver=2)
