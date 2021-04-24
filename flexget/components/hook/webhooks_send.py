from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.components.hook.hook_util import (
    webhooks_config_process,
    hooks_data_process,
    HOOK_SCHEMA_DATA,
    HOOK_SCHEMA_WEBHOOK_DEFAULT,
    WEBHOOK_PLUGIN,
)

PLUGIN_NAME = 'webhooks_send'
logger = logger.bind(name=PLUGIN_NAME)


class WebHooksSend:
    """
    WebHook Output

    Config:
      webhook:
        host: <<target host | required>>
        endpoint: <<target endpoint | optional>>
        method: <<method [GET|POST] | optional (default GET)>>
        headers: <<headers | optional>>
        data: <<data object | otional (default 'accepted entry')

    Exemple:
      webhooks_send:
        host: myhost
        endpoint: 'flexget/accepted
        method: 'POST'
        headers:
            token: 123_API_TOKEN
        data:
            title: '{{title}}'
            imdb: '{{imdb_id}}'
    """

    schema = {
        'type': 'object',
        'properties': {**HOOK_SCHEMA_DATA, **HOOK_SCHEMA_WEBHOOK_DEFAULT},
        'required': ['host'],
        'additionalProperties': False,
    }

    def process_config(self, config):
        config = webhooks_config_process(config)
        config['data'] = hooks_data_process(config.get('data'))
        config.setdefault('title', '')
        config.setdefault('verify_certificates', True)
        return config

    @plugin.priority(0)
    def on_task_output(self, task, config):
        config = self.process_config(config)

        send_webhook = plugin.get_plugin_by_name('hook_framework').instance.send_hook

        config_params = {}
        config_params['host'] = config['host']
        config_params['method'] = config['method']
        config_params['headers'] = config['headers']
        config_params['data'] = config['data']
        config_params['verify_certificates'] = task.requests.verify
        if 'endpoint' in config:
            config_params['endpoint'] = config['endpoint']

        new_config = {WEBHOOK_PLUGIN: {**config_params}}

        for entry in task.accepted:
            send_webhook(config['title'], entry, new_config)


@event('plugin.register')
def register_plugin():
    plugin.register(WebHooksSend, PLUGIN_NAME, api_ver=2)
