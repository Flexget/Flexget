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

plugin_name = 'pushbullet'
log = logging.getLogger(plugin_name)

PUSHBULLET_URL = 'https://api.pushbullet.com/v2/pushes'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('pushbullet.com', '5 seconds'))


class PushbulletNotifier(object):
    """
    Example::

    notify:
      entries:
        via:
          pushbullet:
            apikey: <API_KEY>
            [device: <DEVICE_IDEN> (can also be a list of device ids, or don't specify any ids to send to all devices)]
            [email: <EMAIL_ADDRESS> (can also be a list of user email addresses)]
            [channel: <CHANNEL_TAG> (you can only specify device / email or channel tag, cannot use both)]

    Configuration parameters are also supported from entries (eg. through set).
    """

    schema = {
        'type': 'object',
        'properties': {
            'api_key': one_or_more({'type': 'string'}),
            'device': one_or_more({'type': 'string'}),
            'email': one_or_more({'type': 'string', 'format': 'email'}),
            'url': {'type': 'string'},
            'channel': {'type': 'string'},
            'file_template': {'type': 'string'},
        },
        'required': ['api_key'],
        'oneOf': [
            {'required': ['device']},
            {'required': ['channel']},
            {'required': ['email']},
            {
                'not': {
                    'anyOf': [
                        {'required': ['device']},
                        {'required': ['channel']},
                        {'required': ['email']},
                    ]
                }
            },
        ],
        'error_oneOf': 'One (and only one) of `email`, `device` or `channel` are allowed.',
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send a Pushbullet notification
        """
        if config.get('device') and not isinstance(config['device'], list):
            config['device'] = [config['device']]

        if config.get('email') and not isinstance(config['email'], list):
            config['email'] = [config['email']]

        if not isinstance(config['api_key'], list):
            config['api_key'] = [config['api_key']]

        for key in config['api_key']:
            if config.get('channel'):
                self.send_push(
                    key, title, message, config.get('url'), config.get('channel'), 'channel_tag'
                )
            elif config.get('device'):
                for d in config['device']:
                    self.send_push(key, title, message, config.get('url'), d, 'device_iden')
            elif config.get('email'):
                for e in config['email']:
                    self.send_push(key, title, message, config.get('url'), e, 'email')
            else:
                self.send_push(key, title, message, config.get('url'))

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
            'User-Agent': 'Flexget',
        }
        try:
            response = requests.post(PUSHBULLET_URL, headers=headers, json=notification)
        except RequestException as e:
            if e.response is not None:
                if e.response.status_code == 429:
                    reset_time = datetime.datetime.fromtimestamp(
                        int(e.response.headers['X-Ratelimit-Reset'])
                    ).strftime('%Y-%m-%d %H:%M:%S')
                    message = (
                        'Monthly Pushbullet database operations limit reached. Next reset: %s'
                        % reset_time
                    )
                else:
                    message = e.response.json()['error']['message']
            else:
                message = str(e)
            raise PluginWarning(message)

        reset_time = datetime.datetime.fromtimestamp(
            int(response.headers['X-Ratelimit-Reset'])
        ).strftime('%Y-%m-%d %H:%M:%S')
        remaining = response.headers['X-Ratelimit-Remaining']
        log.debug(
            'Pushbullet notification sent. Database operations remaining until next reset: %s. '
            'Next reset at: %s',
            remaining,
            reset_time,
        )


@event('plugin.register')
def register_plugin():
    plugin.register(PushbulletNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
