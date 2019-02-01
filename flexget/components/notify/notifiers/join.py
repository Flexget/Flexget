from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.config_schema import one_or_more
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

plugin_name = 'join'
log = logging.getLogger(plugin_name)

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('appspot.com', '5 seconds'))

JOIN_URL = 'https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush'


class JoinNotifier(object):
    """
    Example::

      notify:
        entries:
          via:
            - join:
                [api_key: <API_KEY> (your join api key. Only required for 'group' notifications)]
                [group: <GROUP_NAME> (name of group of join devices to notify. 'all', 'android', etc.)
                [device: <DEVICE_ID> (can also be a list of device ids)]
                [url: <NOTIFICATION_URL>]
                [sms_number: <NOTIFICATION_SMS_NUMBER>]
                [icon: <NOTIFICATION_ICON>]
    """

    schema = {
        'type': 'object',
        'properties': {
            'api_key': {'type': 'string'},
            'group': {
                'type': 'string',
                'enum': ['all', 'android', 'chrome', 'windows10', 'phone', 'tablet', 'pc'],
            },
            'device': one_or_more({'type': 'string'}),
            'device_name': one_or_more({'type': 'string'}),
            'url': {'type': 'string'},
            'icon': {'type': 'string'},
            'sms_number': {'type': 'string'},
            'priority': {'type': 'integer', 'minimum': -2, 'maximum': 2},
        },
        'required': ['api_key'],
        'not': {'required': ['device', 'group']},
        'error_not': 'Cannot select both \'device\' and \'group\'',
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send Join notifications.
        """
        notification = {
            'title': title,
            'text': message,
            'url': config.get('url'),
            'icon': config.get('icon'),
            'priority': config.get('priority'),
            'apikey': config['api_key'],
        }
        if config.get('device'):
            if isinstance(config['device'], list):
                notification['deviceIds'] = ','.join(config['device'])
            else:
                notification['deviceId'] = config['device']
        elif config.get('group'):
            notification['deviceId'] = 'group.' + config['group']
        else:
            notification['deviceId'] = 'group.all'

        if config.get('device_name'):
            if isinstance(config['device_name'], list):
                notification['deviceNames'] = ','.join(config['device_name'])
            else:
                notification['deviceNames'] = config['device_name']

        if config.get('sms_number'):
            notification['smsnumber'] = config['sms_number']
            notification['smstext'] = message

        try:
            response = requests.get(JOIN_URL, params=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])
        else:
            error = response.json().get('errorMessage')
            if error:
                raise PluginWarning(error)


@event('plugin.register')
def register_plugin():
    plugin.register(JoinNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
