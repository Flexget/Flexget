from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import aggregate_inputs

logger = logger.bind(name='inputs')


class PluginInputs:
    """
    Allows the same input plugin to be configured multiple times in a task.

    Example::

      inputs:
        - rss: http://feeda.com
        - rss: http://feedb.com
    """

    schema = {
        'type': 'array',
        'items': {
            'allOf': [
                {'$ref': '/schema/plugins?phase=input'},
                {
                    'maxProperties': 1,
                    'error_maxProperties': 'Plugin options within inputs plugin must be indented 2 more spaces than '
                    'the first letter of the plugin name.',
                    'minProperties': 1,
                },
            ]
        },
    }

    def on_task_input(self, task, config):
        return aggregate_inputs(task, config)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginInputs, 'inputs', api_ver=2)
