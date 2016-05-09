from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError

log = logging.getLogger('list_queue')


class ListQueue(object):
    schema = {'type': 'array',
              'items':
                  {'allOf': [
                      {'$ref': '/schema/plugins?group=list'},
                      {
                          'maxProperties': 1,
                          'error_maxProperties': 'Plugin options within list_queue plugin must be indented 2 more spaces '
                                                 'than the first letter of the plugin name.',
                          'minProperties': 1
                      }
                  ]
                  }
              }

    def on_task_filter(self, task, config):
        for item in config:
            for plugin_name, plugin_config in item.items():
                try:
                    thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                except AttributeError:
                    raise PluginError('Plugin %s does not support list interface' % plugin_name)
                cached_items = []
                for entry in task.entries:
                    result = thelist.get(entry)
                    if result and result not in cached_items:
                        entry.accept()
                        cached_items.append(result)

    def on_task_learn(self, task, config):
        for item in config:
            for plugin_name, plugin_config in item.items():
                thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                if task.manager.options.test and thelist.online:
                    log.info('`%s` is marked as online, would remove accepted items outside of --test mode.',
                             plugin_name)
                    continue
                log.verbose('removing accepted entries from %s - %s', plugin_name, plugin_config)
                thelist -= task.accepted


@event('plugin.register')
def register_plugin():
    plugin.register(ListQueue, 'list_queue', api_ver=2)
