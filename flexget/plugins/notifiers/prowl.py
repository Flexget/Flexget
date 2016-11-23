from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

import xml.etree.ElementTree as ET

from flexget import plugin
from flexget.event import event
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
        apikey: xxxxxxx
        [application: application name, default FlexGet]
        [event: event title, default New Release]
        [priority: -2 - 2 (2 = highest), default 0]
        [description: notification to send]

    """
    schema = {
        'type': 'object',
        'properties': {
            'apikey': {'type': 'string'},
            'application': {'type': 'string', 'default': 'FlexGet'},
            'title': {'type': 'string'},
            'priority': {'type': 'integer', 'default': 0},
            'message': {'type': 'string'},
            'url': {'type': 'string'},
            'template': {'type': 'string', 'format': 'template'}
        },
        'required': ['apikey'],
        'additionalProperties': False
    }

    def notify(self, data):
        apikey = data.get('apikey')
        application = data.get('application')
        event = data.get('title')
        priority = data.get('priority')
        description = data.get('message')
        message_url = data.get('url', '')

        message_data = {'priority': priority,
                'application': application,
                'apikey': apikey,
                'event': event,
                'description': description,
                'url': message_url}

        try:
            response = requests.post(PROWL_URL, data=message_data)
        except RequestException as e:
            log.error('Could not connect to prowl: %s', e.args[0])
            return
        request_status = ET.fromstring(response.content)
        error = request_status.find('error')
        if error is not None:
            log.error('Could not send notification: %s', error.text)
        else:
            success = request_status.find('success').attrib
            log.verbose('prowl notification sent. Notifications remaining until next reset: %s. '
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
