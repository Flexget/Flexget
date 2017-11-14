from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils import qualities

log = logging.getLogger('custom_quality')


class CustomQuality(object):
    """Add custom quality components to the task"""

    schema = {
        'type': 'object',
        'additionalProperties': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'object',
                    'properties': {
                        'score': {'type': 'integer', 'minimum': 1, 'default': 10},
                        'regexp': {'type': 'string', 'format': 'regex'}
                    }
                }
            }
        }
    }

    @plugin.priority(255)
    def on_task_start(self, task, config):
        for component_name, custom_qualities in config.items():
            qualities._custom_components.setdefault(component_name, [])
            for custom_quality in custom_qualities:
                name = custom_quality.keys()[0]
                score = custom_quality[name]['score']
                regexp = custom_quality[name].get('regexp')

                component = qualities.QualityComponent(component_name, score, name, regexp)
                qualities._custom_components[component_name].append(component)

    @plugin.priority(0)
    def on_task_exit(self, task, config):
        qualities._custom_components = {}


@event('plugin.register')
def register_plugin():
    plugin.register(CustomQuality, 'custom_quality', api_ver=2)
