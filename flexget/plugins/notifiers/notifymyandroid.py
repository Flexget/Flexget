from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import xml.etree.ElementTree as ET
import requests

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from requests.exceptions import RequestException

__name__ = 'notifymyandroid'
log = logging.getLogger(__name__)

NOTIFYMYANDROID_URL = 'https://www.notifymyandroid.com/publicapi/notify'


class NotifyMyAndroidNotifier(object):
    """
    Example::

      notifymyandroid:
        apikey: xxxxxxx
        [application: application name, default FlexGet]
        [event: event title, default New Release]
        [priority: -2 - 2 (2 = highest), default 0]

    Configuration parameters are also supported from entries (eg. through set).
    """

    schema = {
        'type': 'object',
        'properties': {
            'apikey': one_or_more({'type': 'string'}),
            'application': {'type': 'string', 'default': 'FlexGet'},
            'title': {'type': 'string'},
            'message': {'type': 'string'},
            'priority': {'type': 'integer', 'minimum': -2, 'maximum': 2},
            'developer_key': {'type': 'string'},
            'url': {'type': 'string'},
            'html': {'type': 'boolean'},
            'file_template': {'type': 'string'}
        },
        'required': ['apikey'],
        'additionalProperties': False
    }

    def notify(self, apikey, title, message, application, priority=None, developer_key=None, url=None, html=None):
        """
        Send a Notifymyandroid notification

        :param str apikey: One or more API keys
        :param str title: Event name
        :param str message: Notification message
        :param str application: Application name
        :param int priority: Notification priority
        :param str developer_key: Optional developer key
        :param str url: Notification URL
        :param bool html: Sets `content-type` to `text/html` if True
        """
        notification = {'event': title, 'description': message, 'application': application, 'priority': priority,
                        'developerkey': developer_key, 'url': url}

        # Handle multiple API keys
        if isinstance(apikey, list):
            apikey = ','.join(apikey)

        notification['apikey'] = apikey

        # Special case for html handling
        if html:
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
            log.debug('notifymyandroid notification sent. Notifications remaining until next reset: %s. '
                      'Next reset will occur in %s minutes', success['remaining'], success['resettimer'])

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        # Send default values for backwards compatibility
        notify_config = {
            'to': [{__name__: config}],
            'scope': 'entries',
            'what': 'accepted'
        }
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)


@event('plugin.register')
def register_plugin():
    plugin.register(NotifyMyAndroidNotifier, __name__, api_ver=2, groups=['notifiers'])
