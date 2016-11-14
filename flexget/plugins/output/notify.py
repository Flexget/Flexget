from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

log = logging.getLogger('notify')

HANDLED_PHASES = ['start', 'input', 'filter', 'output', 'exit']


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
            'what': one_or_more({'type': 'string', 'enum': ['entries', 'accepted', 'rejected', 'failed', 'undecided']}),
            'phase': one_or_more({'type': 'string', 'enum': HANDLED_PHASES, 'default': 'output'})
        },
        'required': ['to'],
        'additionalProperties': False
    }

    @staticmethod
    def prepare_config(config):
        if not isinstance(config['phase'], list):
            config['phase'] = [config['phase']]
        if not isinstance(config['what'], list):
            config['what'] = [config['what']]
        config.setdefault('what', ['accepted'])
        config.setdefault('scope', 'entries')
        config.setdefault('phase', ['output'])
        return config

    def send_notification(self, task, phase, config):
        config = self.prepare_config(config)

        if phase not in config['phase']:
            log.debug('phase %s not configured', phase)
            return

        scope = config['scope']

        # In case the request notification scope is `task`, skip all phases other than exit in order not to send
        # more than 1 notification
        if scope == 'task' and phase != 'exit':
            log.debug('skipping phase on_task_%s since scope is `task`', phase)
            return

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

                log.debug('sending a notification to %s', plugin_name)
                notifier.notify(**kwargs)

    def __getattr__(self, item):
        """Creates methods to handle task phases."""
        for phase in HANDLED_PHASES:
            if item == plugin.phase_methods[phase]:
                # A phase method we handle has been requested
                break
        else:
            # We don't handle this phase
            raise AttributeError(item)

        def phase_handler(task, config):
            self.send_notification(task, phase, config)

        # Make sure we run after other plugins
        phase_handler.priority = 255
        return phase_handler


@event('plugin.register')
def register_plugin():
    plugin.register(Notify, 'notify', api_ver=2)
