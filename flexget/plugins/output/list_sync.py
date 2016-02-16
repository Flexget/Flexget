import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('list_sync')


class ListSync(object):
    schema = {
        'type': 'array',
        'items': {
            'allOf': [
                {'$ref': '/schema/plugins?group=list'},
                {
                    'maxProperties': 1,
                    'error_maxProperties': 'Plugin options within list_sync plugin must be indented 2 more spaces '
                                           'than the first letter of the plugin name.',
                    'minProperties': 1
                }
            ]
        }
    }

    def on_task_output(self, task, config):
        for item in config:
            for plugin_name, plugin_config in item.iteritems():
                if task.manager.options.test:
                    log.info('Would sync accepted items to `%s` outside of --test mode.' % plugin_name)
                    continue
                thelist = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
                # Remove any items from the list that aren't in the task
                thelist &= task.accepted
                # Add any extra items from the task that weren't in the list
                thelist |= task.accepted


@event('plugin.register')
def register_plugin():
    plugin.register(ListSync, 'list_sync', api_ver=2)
