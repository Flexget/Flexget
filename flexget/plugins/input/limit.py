from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import itertools
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('limit')


class PluginLimit(object):
    """
    Limits the number of entries an input plugin can produce.
    """

    schema = {
        'type': 'object',
        'properties': {
            'amount': {'type': 'integer', 'minimum': -1},
            'from': {
                'allOf': [
                    {'$ref': '/schema/plugins?phase=input'},
                    {
                        'maxProperties': 1,
                        'error_maxProperties': 'Plugin options within limit plugin must be indented 2 more spaces than '
                        'the first letter of the plugin name.',
                        'minProperties': 1,
                    },
                ]
            },
        },
        'required': ['amount', 'from'],
        'additionalProperties': False,
    }

    def on_task_input(self, task, config):
        for input_name, input_config in config['from'].items():
            input = plugin.get_plugin_by_name(input_name)
            method = input.phase_handlers['input']
            try:
                result = method(task, input_config)
            except plugin.PluginError as e:
                log.warning('Error during input plugin %s: %s' % (input_name, e))
                continue
            # A 0 or -1 limit means don't limit.
            if config['amount'] < 1:
                return result
            return itertools.islice(result, config['amount'])


@event('plugin.register')
def register_plugin():
    plugin.register(PluginLimit, 'limit', api_ver=2)
