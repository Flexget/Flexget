from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('notify')


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
            'what': {'type': 'string', 'enum': ['all', 'accepted', 'rejected', 'failed', 'undecided']}
        },
        'required': ['to'],
        'additionalProperties': False
    }

    @plugin.priority(0)
    def on_task_output(self, task, config):
        for item in config['to']:
            for plugin_name, plugin_config in item.items():
                notifier = plugin.get_plugin_by_name(plugin_name).instance
                scope = config.get('scope', 'entries')
                what = config.get('what', 'accepted')
                if what == 'all':
                    what = 'entries'
                iterate_on = getattr(task, what)
                kwargs = {'task': task,
                          'scope': scope,
                          'iterate_on': iterate_on,
                          'test': task.options.test,
                          'config': plugin_config}
                log.debug('sending a notification to %s', plugin_name)
                notifier.notify(**kwargs)


@event('plugin.register')
def register_plugin():
    plugin.register(Notify, 'notify', api_ver=2)
