from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import base64
import datetime

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

__name__ = 'pushbullet'
log = logging.getLogger(__name__)

PUSHBULLET_URL = 'https://api.pushbullet.com/v2/pushes'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('pushbullet.com', '5 seconds'))


class PushbulletNotifier(object):
    """
    Example::

      pushbullet:
        apikey: <API_KEY>
        [device: <DEVICE_IDEN> (can also be a list of device idens, or don't specify any idens to send to all devices)]
        [email: <EMAIL_ADDRESS> (can also be a list of user email addresses)]
        [channel: <CHANNEL_TAG> (you can only specify device / email or channel tag. cannot use both.)]
        [title: <MESSAGE_TITLE>] (default: "{{task}} - Download started" -- accepts Jinja2)
        [body: <MESSAGE_BODY>] (default: "{{series_name}} {{series_id}}" -- accepts Jinja2)

    Configuration parameters are also supported from entries (eg. through set).
    """
    schema = {
        'type': 'object',
        'properties': {
            'api_key': one_or_more({'type': 'string'}),
            'device': one_or_more({'type': 'string'}),
            'email': one_or_more({'type': 'string', 'format': 'email'}),
            'title': {'type': 'string'},
            'message': {'type': 'string'},
            'url': {'type': 'string'},
            'channel': {'type': 'string'},
            'file_template': {'type': 'string'},
        },
        'not': {
            'anyOf': [
                {'required': ['device', 'email']},
                {'required': ['channel', 'email']},
                {'required': ['channel', 'device']}
            ]},
        'error_not': 'Can only use one of `email`, `device` or `channel`',
        'anyOf': [
            {'required': ['api_key', 'email']},
            {'required': ['api_key', 'device']},
            {'required': ['api_key', 'channel']},
            {'required': ['api_key']}
        ],
        'error_anyOf': '`api_key` is required',
        'additionalProperties': False
    }

    def notify(self, api_key, title, message, device=None, email=None, url=None, channel=None, **kwargs):
        """
        Send a Pushbullet notification

        :param str api_key: one or more api keys
        :param str title: title of notification
        :param str message: message of notification
        :param str device: one or more devices to send to
        :param str email: one or more emails to send to
        :param str url: URL to attach to notification
        :param str channel: Channel to send to
        """
        if device and not isinstance(device, list):
            device = [device]

        if email and not isinstance(email, list):
            email = [email]

        if not isinstance(api_key, list):
            api_key = [api_key]

        for key in api_key:
            if channel:
                self.send_push(key, title, message, url, channel, 'channel_tag')
            elif device:
                for d in device:
                    self.send_push(key, title, message, url, d, 'device_iden')
            elif email:
                for e in email:
                    self.send_push(key, title, message, url, e, 'email')
            else:
                self.send_push(key, title, message, url)

    def send_push(self, api_key, title, body, url=None, destination=None, destination_type=None):
        push_type = 'link' if url else 'note'
        notification = {'type': push_type, 'title': title, 'body': body}
        if url:
            notification['url'] = url
        if destination:
            notification[destination_type] = destination

        # Make the request
        headers = {
            'Authorization': b'Basic ' + base64.b64encode(api_key.encode('ascii')),
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Flexget'
        }
        try:
            response = requests.post(PUSHBULLET_URL, headers=headers, json=notification)
        except RequestException as e:
            if e.response is not None:
                if e.response.status_code == 429:
                    reset_time = datetime.datetime.fromtimestamp(
                        int(e.response.headers['X-Ratelimit-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
                    message = 'Monthly Pushbullet database operations limit reached. Next reset: %s' % reset_time
                else:
                    message = e.response.json()['error']['message']
            else:
                message = str(e)
            raise PluginWarning(message)

        reset_time = datetime.datetime.fromtimestamp(
            int(response.headers['X-Ratelimit-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
        remaining = response.headers['X-Ratelimit-Remaining']
        log.debug('Pushbullet notification sent. Database operations remaining until next reset: %s. '
                  'Next reset at: %s', remaining, reset_time)

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
    plugin.register(PushbulletNotifier, __name__, api_ver=2, groups=['notifiers'])
