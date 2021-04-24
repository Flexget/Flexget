from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.components.hook.hook_util import (
    HOOK_SCHEMA_DEFAULT,
    webhooks_config_process,
    hooks_data_process,
)

PLUGIN_NAME = 'notifyhooks'
logger = logger.bind(name=PLUGIN_NAME)


class NotifyHooks:
    """
    Provides a bridge to send hooks on any notify plugin

    Config:
      notifyhooks:
        title: <<title | optional>>
        data: <<data object | otional (default 'task data')
        verify_certificates: <<verify [yes|no] | optional (default yes)>>
      via
        - <<notify plugin>>


    Exemple:
    notifyhooks:
        title: '{{task_name}}'
        data: Running task {{task_name}} in {{event_type}} {{event_name}} {{event_stage}}, got {{accepted|length}} accepted
        via:
            - telegram:
                bot_token: "<<token>>"
                parse_mode: html
                recipients:
                - {username: "<<username>>"}

    """

    schema = {
        'type': 'object',
        'properties': {
            **HOOK_SCHEMA_DEFAULT,
            'verify_certificates': {'type': 'boolean'},
            'via': {
                'type': 'array',
                'items': {
                    'allOf': [
                        {'$ref': '/schema/plugins?interface=notifiers'},
                        {
                            'maxProperties': 1,
                            'error_maxProperties': 'Plugin options indented 2 more spaces than '
                            'the first letter of the plugin name.',
                            'minProperties': 1,
                        },
                    ]
                },
            },
        },
        'additionalProperties': False,
    }

    def process_config(self, config: dict):
        config = webhooks_config_process(config)

        if 'data' in config:
            config['data'] = hooks_data_process(config.get('data'))

        config.setdefault('verify_certificates', True)
        config.setdefault('via', [])

        return config

    def send_hook(self, title, data, config):
        config = self.process_config(config)

        if 'data' in config:
            config['data'] = hooks_data_process(config.get('data'))

        data_default = hooks_data_process(data)
        title_default = title

        via = config['via']
        data = config.get('data', data_default)
        title = config.get('title', title_default)

        message = data

        send_notification = plugin.get_plugin_by_name(
            'notification_framework'
        ).instance.send_notification

        send_notification(title, message, via)


@event('plugin.register')
def register_plugin():
    plugin.register(NotifyHooks, PLUGIN_NAME, api_ver=2, interfaces=['hooks'])
