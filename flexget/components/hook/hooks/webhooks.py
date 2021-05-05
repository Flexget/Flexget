from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import requests
from flexget.plugin import PluginError
from flexget.components.hook.hook_util import (
    jsonify,
    webhooks_config_process,
    hooks_data_process,
    HOOK_SCHEMA_DEFAULT,
    HOOK_SCHEMA_WEBHOOK_DEFAULT,
    WEBHOOK_PLUGIN,
)


PLUGIN_NAME = WEBHOOK_PLUGIN
logger = logger.bind(name=PLUGIN_NAME)


class WebHooks:
    """
    WebHook Hook

    Config:
      webhook:
        host: <<target host | required>>
        endpoint: <<target endpoint | optional (default 'event'/'name'/'stage')>>
        method: <<method [GET|POST] | optional (default GET)>>
        headers: <<headers | optional>>
        send_data: <<data object | otional (default 'task data')
        verify_certificates: <<verify [yes|no] | optional (default yes)>>

    Exemple:
      webhook:
        host: myhost
        endpoint: 'flexget/accepted
        method: 'POST'
        headers:
            token: 123_API_TOKEN
        send_data:
            title: '{{title}}'
            imdb: '{{imdb_id}}'
    """

    schema = {
        'type': 'object',
        'properties': {
            **HOOK_SCHEMA_WEBHOOK_DEFAULT,
            **HOOK_SCHEMA_DEFAULT,
            'verify_certificates': {'type': 'boolean'},
        },
        'required': ['host'],
        'additionalProperties': False,
    }

    def process_config(self, config: dict):
        config = webhooks_config_process(config)

        if 'send_data' in config:
            config['send_data'] = hooks_data_process(config.get('send_data'))

        config.setdefault('verify_certificates', True)

        return config

    def send_hook(self, title, send_data, config):
        config = self.process_config(config)

        event_tree = send_data.get('event_tree', [])

        data_default = hooks_data_process(send_data)
        title_default = title

        host = config.get('host')
        endpoint = config.get('endpoint', '/'.join(event_tree))
        send_data = config.get('send_data', data_default)
        title = config.get('title', title_default)

        url = f'{host}/{endpoint}'

        try:
            if config['method'] == 'GET':
                if isinstance(send_data, (dict, list)):
                    send_data = jsonify(send_data)

                response = requests.get(
                    url,
                    params=send_data,
                    headers=config['headers'],
                    allow_redirects=True,
                    verify=config['verify_certificates'],
                )
            elif config['method'] == 'POST':
                params = {}
                if isinstance(send_data, (dict, list)):
                    params['json'] = send_data
                else:
                    params['send_data'] = send_data

                response = requests.post(
                    url,
                    headers=config['headers'],
                    allow_redirects=True,
                    verify=config['verify_certificates'],
                    **params,
                )
        except RequestException as error:
            raise PluginError('Could not send WebHook: %s' % str(error)) from error


@event('plugin.register')
def register_plugin():
    plugin.register(WebHooks, PLUGIN_NAME, api_ver=2, interfaces=['hooks'])
