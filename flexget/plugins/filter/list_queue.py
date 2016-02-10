import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('list_queue')


class ListQueue(object):
    schema = {
        'type': 'array',
        'items': {
            'allOf': [
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
            for plugin_name, plugin_config in item.iteritems():
                thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                for entry in task.all_entries:
                    if entry in thelist:
                        entry.accept()

    def on_task_learn(self, task, config):
        for item in config:
            for plugin_name, plugin_config in item.iteritems():
                thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                thelist -= task.accepted


@event('plugin.register')
def register_plugin():
    plugin.register(ListQueue, 'list_queue', api_ver=2)
