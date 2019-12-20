from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session

plugin_name = 'ifttt'
logger = logger.bind(name=plugin_name)


class IFTTTNotifier:
    """
    Push the notification to an IFTTT webhook.

    Configuration options

    ===============  ===================================================================
    Option           Description
    ===============  ===================================================================
    event            The event endpoint to trigger (required)
    keys             List of auth  keys to send the notification to. (required)
    ===============  ===================================================================

    Config basic example::

      notify:
        task:
          via:
            - ifttt:
                event: download_added
                keys:
                    - deadebeef123
    """

    def __init__(self):
        self.session = Session()
        self.url_template = 'https://maker.ifttt.com/trigger/{}/with/key/{}'

    schema = {
        'type': 'object',
        'properties': {'event': {'type': 'string'}, 'keys': one_or_more({'type': 'string'})},
        'required': ['event', 'keys'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send notification to ifttt webhook.

        The notification will be sent to https://maker.ifttt.com/trigger/{event}/with/key/{key}'
        with the values for the config, with a json body setting 'value1' to the message title,
        and 'value2' to the message body.

        If multiple keys are provided the event will be triggered for all of them.

        :param str message: message body
        :param str title: message subject
        :param dict config: plugin config
        """
        config = self.prepare_config(config)
        notification_body = {'value1': title, 'value2': message}
        errors = False
        for key in config['keys']:
            url = self.url_template.format(config['event'], key)
            try:
                self.session.post(url, json=notification_body)
                logger.info('Sent notification to key: {}', key)
            except RequestException as e:
                logger.error('Error sending notification to key {}: {}', key, e)
                errors = True
        if errors:
            raise PluginWarning("Failed to send notifications")

    def prepare_config(self, config):
        if not isinstance(config['keys'], list):
            config['keys'] = [config['keys']]
        return config


@event('plugin.register')
def register_plugin():
    plugin.register(IFTTTNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
