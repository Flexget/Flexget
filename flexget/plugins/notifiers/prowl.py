from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import xml.etree.ElementTree as ET

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

__name__ = 'prowl'
log = logging.getLogger(__name__)

PROWL_URL = 'https://api.prowlapp.com/publicapi/add'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('prowlapp.com', '5 seconds'))


class ProwlNotifier(object):
    """
    Send prowl notifications

    Example::

      prowl:
        api_key: xxxxxxx
        [application: application name, default FlexGet]
        [event: event title, default New Release]
        [priority: -2 - 2 (2 = highest), default 0]
        [description: notification to send]

    """
    schema = {
        'type': 'object',
        'properties': {
            'api_key': one_or_more({'type': 'string'}),
            'application': {'type': 'string', 'default': 'FlexGet'},
            'title': {'type': 'string'},
            'priority': {'type': 'integer', 'minimum': -2, 'maximum': 2},
            'message': {'type': 'string'},
            'url': {'type': 'string'},
            'provider_key':{'type': 'string'},
            'file_template': {'type': 'string'}
        },
        'required': ['api_key'],
        'additionalProperties': False
    }

    def notify(self, api_key, application, title, message, priority=None, provider_key=None, url=None, **kwargs):
        """
        Send a Prowl notification

        :param str api_key: One or more API keys
        :param str application: Application name
        :param str title: Notification subject
        :param str message: Notification message
        :param priority: Notification priority
        :param str provider_key: Your provider API key. Only necessary if you have been whitelisted.
        :param str url: The URL which should be attached to the notification.
        """
        notification = {'application': application, 'event': title, 'description': message, 'url': url,
                        'priority': priority, 'providerkey': provider_key}

        if isinstance(api_key, list):
            api_key = [api_key]
        notification['apikey'] = api_key

        try:
            response = requests.post(PROWL_URL, data=notification)
        except RequestException as e:
            raise PluginWarning(repr(e))

        request_status = ET.fromstring(response.content)
        error = request_status.find('error')
        if error is not None:
            raise PluginWarning(error.text)
        else:
            success = request_status.find('success').attrib
            log.debug('prowl notification sent. Notifications remaining until next reset: %s. '
                      'Next reset will occur in %s minutes', success['remaining'], success['resetdate'])

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
    plugin.register(ProwlNotifier, __name__, api_ver=2, groups=['notifiers'])
