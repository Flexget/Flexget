from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

log = logging.getLogger('notify')

ENTRY_CONTAINERS = ['entries', 'accepted', 'rejected', 'failed', 'undecided']


class Notify(object):
    schema = {
        'type': 'object',
        'properties': {
            'to': {'type': 'array', 'items':
                {'allOf': [
                    {'$ref': '/schema/plugins?group=notifiers'},
                    {'maxProperties': 1,
                     'error_maxProperties': 'Plugin options within notify plugin must be indented '
                                            '2 more spaces than the first letter of the plugin name.',
                     'minProperties': 1}]}},
            'scope': {'type': 'string', 'enum': ['task', 'entries']},
            'what': one_or_more({'type': 'string', 'enum': ENTRY_CONTAINERS})
        },
        'required': ['to'],
        'additionalProperties': False
    }

    @staticmethod
    def prepare_config(config):
        config.setdefault('what', ['accepted'])
        if not isinstance(config['what'], list):
            config['what'] = [config['what']]
        config.setdefault('scope', 'entries')
        return config

    def send_notification(self, task, config):
        config = self.prepare_config(config)
        scope = config['scope']
        what = config['what']

        # Build a list of entry containers or just uses task, depending on the scope
        iterate_on = [getattr(task, container) for container in what]

        for item in config['to']:
            for plugin_name, plugin_config in item.items():
                notifier = plugin.get_plugin_by_name(plugin_name).instance

                kwargs = {'task': task,
                          'scope': scope,
                          'iterate_on': iterate_on,
                          'test': task.options.test,
                          'config': plugin_config}

                log.info('Sending a notification to %s', plugin_name)
                notifier.notify(**kwargs)

    def on_task_start(self, task, config):
        # Suppress warnings about missing output plugins
        if 'output' not in task.suppress_warnings:
            task.suppress_warnings.append('output')

    on_task_exit = send_notification


@event('plugin.register')
def register_plugin():
    plugin.register(Notify, 'notify', api_ver=2)
