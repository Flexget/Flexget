import xml.etree.ElementTree as ET

import requests
from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning

plugin_name = 'notifymyandroid'
logger = logger.bind(name=plugin_name)

NOTIFYMYANDROID_URL = 'https://www.notifymyandroid.com/publicapi/notify'


class NotifyMyAndroidNotifier:
    """
    Example::

      notify:
        entries:
          via:
            - notifymyandroid:
                apikey: xxxxxxx
                [application: application name, default FlexGet]
                [event: event title, default New Release]
                [priority: -2 - 2 (2 = highest), default 0]

    Configuration parameters are also supported from entries (eg. through set).
    """

    schema = {
        'type': 'object',
        'properties': {
            'api_key': one_or_more({'type': 'string'}),
            'application': {'type': 'string', 'default': 'FlexGet'},
            'priority': {'type': 'integer', 'minimum': -2, 'maximum': 2},
            'developer_key': {'type': 'string'},
            'url': {'type': 'string'},
            'html': {'type': 'boolean'},
        },
        'required': ['api_key'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send a Notifymyandroid notification
        """
        notification = {
            'event': title,
            'description': message,
            'application': config.get('application'),
            'priority': config.get('priority'),
            'developerkey': config.get('developer_key'),
            'url': config.get('url'),
        }

        # Handle multiple API keys
        if isinstance(config['api_key'], list):
            config['api_key'] = ','.join(config['api_key'])

        notification['apikey'] = config['api_key']

        # Special case for html handling
        if config.get('html'):
            notification['content-type'] = 'text/html'

        try:
            response = requests.post(NOTIFYMYANDROID_URL, data=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])

        request_status = ET.fromstring(response.content)
        error = request_status.find('error')
        if error is not None:
            raise PluginWarning(error.text)
        else:
            success = request_status.find('success').attrib
            logger.debug(
                'notifymyandroid notification sent. Notifications remaining until next reset: {}. '
                'Next reset will occur in {} minutes',
                success['remaining'],
                success['resettimer'],
            )


@event('plugin.register')
def register_plugin():
    plugin.register(NotifyMyAndroidNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
