from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.template import RenderError

log = logging.getLogger('notify')

ENTRY_CONTAINERS = ['entries', 'accepted', 'rejected', 'failed', 'undecided']


class Notify(object):
    defaults = {
        'task': {
            'message': 'Task returned {{ task.accepted|length }} accepted entries'
        },
        'entries': {
            'message': '{% if series_name is defined %}'
                       '{{ tvdb_series_name|d(series_name) }} '
                       '{{series_id}} {{tvdb_ep_name|d('')}}'
                       '{% elif imdb_name is defined %}'
                       '{{imdb_name}} {{imdb_year}}'
                       '{% elif title is defined %}'
                       '{{ title }}',
            'url': '{% if imdb_url is defined %}{{imdb_url}}{% endif %}',
            'title': '{{ task_name }}'
        }
    }

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
        'additionalProperties': True
    }

    @staticmethod
    def prepare_config(config):
        config.setdefault('what', ['accepted'])
        if not isinstance(config['what'], list):
            config['what'] = [config['what']]
        config.setdefault('scope', 'entries')
        return config

    @staticmethod
    def render_value(entity, template, attribute, default):
        result = template
        try:
            result = entity.render(template)
        except (RenderError, ValueError) as e:
            log.debug('failed to render: %s', e.args[0])
            try:
                result = entity.render(default[attribute])
            except RenderError as e:
                log.warning('failed to render: %s', e.args[0])
            except KeyError as e:
                log.debug('tried to render a non existing value `%s` from defaults, skipping', attribute)
        return result

    def send_notification(self, task, config):
        config = self.prepare_config(config)
        scope = config.pop('scope')
        what = config.pop('what')
        notifiers = config.pop('to')

        if scope == 'entries':
            iterate_on = [getattr(task, container) for container in what]
        else:
            iterate_on = [[task]]

        for item in notifiers:
            for plugin_name, plugin_config in item.items():
                notifier = plugin.get_plugin_by_name(plugin_name).instance

                for container in iterate_on:
                    for entity in container:
                        message_data = plugin_config
                        for attribute, value in message_data.items():
                            message_data[attribute] = self.render_value(entity, value, attribute, self.defaults[scope])

                        if not task.options.test:
                            log.info('Sending a notification to %s', plugin_name)
                            notifier.notify(message_data)
                        else:
                            log.info('Test mode, would have sent notification with data %s to %s', message_data,
                                     plugin_name)

    def on_task_start(self, task, config):
        # Suppress warnings about missing output plugins
        if 'output' not in task.suppress_warnings:
            task.suppress_warnings.append('output')

    on_task_exit = send_notification


@event('plugin.register')
def register_plugin():
    plugin.register(Notify, 'notify', api_ver=2)
