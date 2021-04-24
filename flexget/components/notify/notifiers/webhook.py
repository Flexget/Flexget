from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.components.hook.hook_util import (
    HOOK_SCHEMA_WEBHOOK_DEFAULT,
    HOOK_SCHEMA_DATA,
    WEBHOOK_PLUGIN,
)

PLUGIN_NAME = 'webhook'
logger = logger.bind(name=PLUGIN_NAME)
DEFAULT_ENDPOINT = 'flexget/notify'


class WebHookNotify:
    """
    WebHook notification

    Config:
      webhook:
        host: <<target host | required>>
        endpoint: <<target endpoint | optional (default flexget/notify)>>
        method: <<method [GET|POST] | optional (default GET)>>
        headers: <<headers | optional>>
        data: <<data object | otional (default {'title':'notify title','message':'notify message'})
        verify_certificates: <<verify [yes|no] | optional (default yes)>>

    Exemple:
      webhook:
        host: myhost
        endpoint: 'flexget/downloaded
        method: 'POST'
        headers:
            token: 123_API_TOKEN
        data:
            title: '{{title}}'
            imdb: '{{imdb_id}}'
    """

    schema = {
        'type': 'object',
        'properties': {
            'verify_certificates': {'type': 'boolean'},
            **HOOK_SCHEMA_WEBHOOK_DEFAULT,
            **HOOK_SCHEMA_DATA,
        },
        'required': ['host'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send a WebHook notification
        """

        config.setdefault('endpoint', DEFAULT_ENDPOINT)

        logger.debug(self.schema)
        send_webhook = plugin.get_plugin_by_name('hook_framework').instance.send_hook
        data = {"title": title, "message": message}
        new_config = {WEBHOOK_PLUGIN: {**config}}
        send_webhook(title, data, new_config)


@event('plugin.register')
def register_plugin():
    plugin.register(WebHookNotify, PLUGIN_NAME, api_ver=2, interfaces=['notifiers'])
