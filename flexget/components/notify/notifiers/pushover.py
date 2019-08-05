from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import datetime
import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

plugin_name = 'pushover'
log = logging.getLogger(plugin_name)

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('pushover.net', '5 seconds'))


class PushoverNotifier(object):
    """
    Example::

      notify:
        entries:
          via:
            - pushover:
                user_key: <USER_KEY> (can also be a list of userkeys)
                token: <TOKEN>
                [device: <DEVICE_STRING>]
                [priority: <PRIORITY>]
                [url: <URL>]
                [url_title: <URL_TITLE>]
                [sound: <SOUND>]
                [retry]: <RETRY>]
                [expire]: <EXPIRE>]
                [callback]: <CALLBACK>]
                [html]: <HTML>]
    """

    schema = {
        'type': 'object',
        'properties': {
            'user_key': one_or_more({'type': 'string'}),
            'api_key': {'type': 'string', 'default': 'aPwSHwkLcNaavShxktBpgJH4bRWc3m'},
            'device': one_or_more({'type': 'string'}),
            'priority': {
                'oneOf': [{'type': 'number', 'minimum': -2, 'maximum': 2}, {'type': 'string'}]
            },
            'url': {'type': 'string'},
            'url_title': {'type': 'string'},
            'sound': {'type': 'string'},
            'retry': {'type': 'integer', 'minimum': 30},
            'expire': {'type': 'integer', 'maximum': 86400},
            'callback': {'type': 'string'},
            'html': {'type': 'boolean'},
        },
        'required': ['user_key'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Sends a Pushover notification

        :param str title: the message's title
        :param str message: the message to send
        :param dict config: The pushover config
        """
        notification = {
            'token': config.get('api_key'),
            'message': message,
            'title': title,
            'device': config.get('device'),
            'priority': config.get('priority'),
            'url': config.get('url'),
            'url_title': config.get('url_title'),
            'sound': config.get('sound'),
            'retry': config.get('retry'),
            'expire': config.get('expire'),
            'callback': config.get('callback'),
        }

        # HTML parsing mode
        if config.get('html'):
            notification['html'] = 1

        # Support multiple devices
        if isinstance(notification['device'], list):
            notification['device'] = ','.join(notification['device'])

        # Special case, verify certain fields exists if priority is 2
        priority = config.get('priority')
        expire = config.get('expire')
        retry = config.get('retry')
        if priority == 2 and not all([expire, retry]):
            log.warning(
                'Priority set to 2 but fields "expire" and "retry" are not both present.Lowering priority to 1'
            )
            notification['priority'] = 1

        if not isinstance(config['user_key'], list):
            config['user_key'] = [config['user_key']]

        for user in config['user_key']:
            notification['user'] = user
            try:
                response = requests.post(PUSHOVER_URL, data=notification)
            except RequestException as e:
                if e.response is not None:
                    if e.response.status_code == 429:
                        reset_time = datetime.datetime.fromtimestamp(
                            int(e.response.headers['X-Limit-App-Reset'])
                        ).strftime('%Y-%m-%d %H:%M:%S')
                        error_message = (
                            'Monthly pushover message limit reached. Next reset: %s' % reset_time
                        )
                    else:
                        error_message = e.response.json()['errors'][0]
                else:
                    error_message = str(e)
                raise PluginWarning(error_message)

            reset_time = datetime.datetime.fromtimestamp(
                int(response.headers['X-Limit-App-Reset'])
            ).strftime('%Y-%m-%d %H:%M:%S')
            remaining = response.headers['X-Limit-App-Remaining']
            log.debug(
                'Pushover notification sent. Notifications remaining until next reset: %s. '
                'Next reset at: %s',
                remaining,
                reset_time,
            )


@event('plugin.register')
def register_plugin():
    plugin.register(PushoverNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
