from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError

logger = logger.bind(name='list_remove')


class ListRemove:
    schema = {
        'type': 'array',
        'items': {
            'allOf': [
                {'$ref': '/schema/plugins?interface=list'},
                {
                    'maxProperties': 1,
                    'error_maxProperties': 'Plugin options within list_remove plugin must be indented 2 more spaces '
                    'than the first letter of the plugin name.',
                    'minProperties': 1,
                },
            ]
        },
    }

    def on_task_output(self, task, config):
        if not len(task.accepted) > 0:
            logger.debug('no accepted entries, nothing to remove')
            return

        for item in config:
            for plugin_name, plugin_config in item.items():
                try:
                    thelist = plugin.get(plugin_name, self).get_list(plugin_config)
                except AttributeError:
                    raise PluginError('Plugin %s does not support list interface' % plugin_name)
                if task.manager.options.test and thelist.online:
                    logger.info(
                        '`{}` is marked as online, would remove accepted items outside of --test mode.',
                        plugin_name,
                    )
                    continue
                logger.verbose(
                    'removing accepted entries from {} - {}', plugin_name, plugin_config
                )
                thelist -= task.accepted


@event('plugin.register')
def register_plugin():
    plugin.register(ListRemove, 'list_remove', api_ver=2)
