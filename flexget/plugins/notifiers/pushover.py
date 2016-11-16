from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import datetime
import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from flexget.utils.template import RenderError
from requests.exceptions import RequestException

log = logging.getLogger('pushover')

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'
NUMBER_OF_RETRIES = 3

requests = RequestSession(max_retries=5)
requests.add_domain_limiter(TimedLimiter('api.pushover.net.cc', '5 seconds'))


class PushoverNotifier(object):
    """
    Example::

      pushover:
        userkey: <USER_KEY> (can also be a list of userkeys)
        apikey: <API_KEY>
        [device: <DEVICE_STRING>] (default: (none))
        [title: <MESSAGE_TITLE>] (default: "Download started" -- accepts Jinja2)
        [message: <MESSAGE_BODY>] (default uses series/tvdb name and imdb if available -- accepts Jinja2)
        [priority: <PRIORITY>] (default = 0 -- normal = 0, high = 1, silent = -1, emergency = 2)
        [url: <URL>] (default: "{{imdb_url}}" -- accepts Jinja2)
        [urltitle: <URL_TITLE>] (default: (none) -- accepts Jinja2)
        [sound: <SOUND>] (default: pushover default)
        [retry]: <RETRY>]

    """

    schema = {
        'type': 'object',
        'properties': {
            'userkey': one_or_more({'type': 'string'}),
            'token': {'type': 'string'},
            'device': {'type': 'string'},
            'title': {'type': 'string'},
            'message': {'type': 'string'},
            'priority': {'oneOf': [
                {'type': 'number', 'minimum': -2, 'maximum': 2},
                {'type': 'string'}]},
            'url': {'type': 'string'},
            'url_title': {'type': 'string'},
            'sound': {'type': 'string'},
            'retry': {'type': 'integer', 'minimum': 30},
            'expire': {'type': 'integer', 'maximum': 86400},
            'callback': {'type': 'string', 'format': 'url'},
            'html': {'type': 'boolean'}
        },
        'required': ['userkey', 'token'],
        'additionalProperties': False
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        # Send default values for backwards compatibility
        notify_config = {
            'to': [{'pushover': config}],
            'scope': 'entries',
            'what': 'accepted'
        }
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)

    @staticmethod
    def notify(data):
        # Special case for html key
        if data.get('html'):
            data['html'] = 1

        # Special case, verify certain fields exists if priority is 2
        if data.get('priority') == 2 and not all([data.get('expire'), data.get('retry')]):
            log.warning('Priority set to 2 but fields "expire" and "retry" are not both present.'
                        ' Lowering priority to 1')
            data['priority'] = 1

        if not isinstance(data['userkey'], list):
            data['userkey'] = [data['userkey']]

        message_data = data
        for user in data['userkey']:
            message_data['user'] = user
            try:
                response = requests.post(PUSHOVER_URL, data=message_data)
            except RequestException as e:
                if e.response.status_code == 429:
                    reset_time = datetime.datetime.fromtimestamp(
                        int(e.response.headers['X-Limit-App-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
                    message = 'Monthly pushover message limit reached. Next reset: %s', reset_time
                else:
                    message = 'Could not send notification to Pushover: %s', e.response.json()['errors']
                log.error(*message)
                return

            reset_time = datetime.datetime.fromtimestamp(
                int(response.headers['X-Limit-App-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
            remaining = response.headers['X-Limit-App-Remaining']
            log.verbose('Pushover notification sent. Notifications remaining until next reset: %s. '
                        'Next reset at: %s', remaining, reset_time)


@event('plugin.register')
def register_plugin():
    plugin.register(PushoverNotifier, 'pushover', api_ver=2, groups=['notifiers'])
