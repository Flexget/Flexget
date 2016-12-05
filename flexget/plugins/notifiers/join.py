from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.config_schema import one_or_more
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

__name__ = 'join'
log = logging.getLogger(__name__)

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('appspot.com', '5 seconds'))

JOIN_URL = 'https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush'


class JoinNotifier(object):
    """
    Example::

      join:
        [api_key: <API_KEY> (your join api key. Only required for 'group' notifications)]
        [group: <GROUP_NAME> (name of group of join devices to notify. 'all', 'android', etc.)
        [device: <DEVICE_ID> (can also be a list of device ids)]
        [title: <NOTIFICATION_TITLE>]
        [message: <NOTIFICATION_TEXT>]
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
                'enum': ['all', 'android', 'chrome', 'windows10', 'phone', 'tablet', 'pc']
            },
            'device': one_or_more({'type': 'string'}),
            'title': {'type': 'string'},
            'body': {'type': 'string'},
            'url': {'type': 'string'},
            'icon': {'type': 'string'},
            'sms_number': {'type': 'string'},
            'priority': {'type': 'integer', 'minimum': -2, 'maximum': 2}
        },
        'dependencies': {
            'group': ['api_key']
        },
        'error_dependencies': '`api_key` is required to use Join `group` notifications',
        'oneOf': [
            {'required': ['device']},
            {'required': ['api_key']},
        ],
        'error_oneOf': 'Either a `device` to notify, or an `api_key` must be specified, and not both',
        'additionalProperties': False
    }

    def notify(self, title, message, url, api_key=None, device=None, group=None, sms_number=None, icon=None,
               priority=None, **kwargs):
        """
        Send Join notifications.

        :param str title: Title of notification
        :param str message: Message of notification
        :param str url: A URL you want to open on the device. If a notification is created with this push,
            this will make clicking the notification open this URL
        :param str api_key: Your API key
        :param str device: One or more device IDs
        :param str group: Groups to send to. One of 'all', 'android', 'chrome', 'windows10', 'phone', 'tablet' or 'pc'
        :param str sms_number: Send a notification to this SMS number
        :param str icon: Notification icon
        :param str priority: Notification priority
        """
        notification = {'title': title, 'text': message, 'url': url, 'icon': icon, 'priority': priority}
        if api_key:
            if not group:
                group = 'all'
            notification['apikey'] = api_key
            notification['deviceId'] = 'group.' + group
        else:
            if isinstance(device, list):
                notification['deviceIds'] = ','.join(device)
            else:
                notification['deviceId'] = device

        if sms_number:
            notification['smsnumber'] = sms_number
            notification['smstext'] = message

        try:
            response = requests.get(JOIN_URL, params=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])
        else:
            error = response.json().get('errorMessage')
            if error:
                raise PluginWarning(error)

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        notify_config = {
            'to': [{__name__: config}],
            'scope': 'entries',
            'what': 'accepted'
        }
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)


@event('plugin.register')
def register_plugin():
    plugin.register(JoinNotifier, __name__, api_ver=2, groups=['notifiers'])
