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

__name__ = 'pushover'
log = logging.getLogger(__name__)

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('pushover.net', '5 seconds'))


class PushoverNotifier(object):
    """
    Example::

      pushover:
        user_key: <USER_KEY> (can also be a list of userkeys)
        token: <TOKEN>
        [device: <DEVICE_STRING>]
        [title: <MESSAGE_TITLE>]
        [message: <MESSAGE_BODY>]
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
            'title': {'type': 'string'},
            'message': {'type': 'string'},
            'priority': {'oneOf': [
                {'type': 'number', 'minimum': -2, 'maximum': 2},
                {'type': 'string'}]},
            'url': {'type': 'string'},
            'url_title': {'type': 'string'},
            'sound': {'type': 'string'},
            'file_template': {'type': 'string'},
            'retry': {'type': 'integer', 'minimum': 30},
            'expire': {'type': 'integer', 'maximum': 86400},
            'callback': {'type': 'string'},
            'html': {'type': 'boolean'}
        },
        'required': ['user_key'],
        'additionalProperties': False
    }

    def notify(self, user_key, api_key, message, title=None, device=None, priority=None, url=None, url_title=None,
               sound=None, retry=None, expire=None, callback=None, html=None, **kwargs):
        """
        Sends a Pushover notification

        :param str user_key: the user/group key or list of them
        :param str api_key: your application's API api_key. Default is 'aPwSHwkLcNaavShxktBpgJH4bRWc3m',
            official Flexget's API key
        :param str message: the message to send
        :param str title: your message's title, otherwise your app's name is used
        :param str device: your user's device name to send the message directly to that device,
            rather than all of the user's devices. Can be a list
        :param int priority: notification priority, int between -2 and 2
        :param str url: a supplementary URL to show with your message
        :param str url_title: a title for your supplementary URL, otherwise just the URL is shown
        :param str sound: the name of one of the sounds supported by device clients to override the user's default
            sound choice
        :param int retry: how often (in seconds) the Pushover servers will send the same notification to the user
        :param int expire: how many seconds your notification will continue to be retried for (every retry seconds).
        :param str callback: a publicly-accessible URL that our servers will send a request to when the user has
            acknowledged your notification
        :param bool html: enable HTML parsing
        """
        notification = {'token': api_key, 'message': message, 'title': title, 'device': device, 'priority': priority,
                        'url': url, 'url_title': url_title, 'sound': sound, 'retry': retry, 'expire': expire,
                        'callback': callback}

        # HTML parsing mode
        if html:
            notification['html'] = 1

        # Support multiple devices
        if isinstance(device, list):
            notification['device'] = ','.join(device)

        # Special case, verify certain fields exists if priority is 2
        if priority == 2 and not all([expire, retry]):
            log.warning('Priority set to 2 but fields "expire" and "retry" are not both present.Lowering priority to 1')
            notification['priority'] = 1

        if not isinstance(user_key, list):
            user_key = [user_key]

        for user in user_key:
            notification['user'] = user
            try:
                response = requests.post(PUSHOVER_URL, data=notification)
            except RequestException as e:
                if e.response is not None:
                    if e.response.status_code == 429:
                        reset_time = datetime.datetime.fromtimestamp(
                            int(e.response.headers['X-Limit-App-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
                        error_message = 'Monthly pushover message limit reached. Next reset: %s' % reset_time
                    else:
                        error_message = e.response.json()['errors'][0]
                else:
                    error_message = str(e)
                raise PluginWarning(error_message)

            reset_time = datetime.datetime.fromtimestamp(
                int(response.headers['X-Limit-App-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
            remaining = response.headers['X-Limit-App-Remaining']
            log.debug('Pushover notification sent. Notifications remaining until next reset: %s. '
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
    plugin.register(PushoverNotifier, __name__, api_ver=2, groups=['notifiers'])
