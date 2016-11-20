from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import base64
import datetime

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

log = logging.getLogger('pushbullet')

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
    default_body = ('{% if series_name is defined %}{{tvdb_series_name|d(series_name)}} {{series_id}} '
                    '{{tvdb_ep_name|d('')}}{% elif imdb_name is defined %}{{imdb_name}} '
                    '{{imdb_year}}{% else %}{{title}}{% endif %}')
    schema = {
        'type': 'object',
        'properties': {
            'apikey': one_or_more({'type': 'string'}),
            'device': one_or_more({'type': 'string'}),
            'email': one_or_more({'type': 'string'}),
            'title': {'type': 'string', 'default': '{{task}} - Download started'},
            'body': {'type': 'string', 'default': default_body},
            'url': {'type': 'string'},
            'channel': {'type': 'string'}
        },
        'required': ['apikey'],
        'additionalProperties': False
    }

    def notify(self, data):
        devices = data.get('device', [])
        if not isinstance(devices, list):
            devices = [devices]

        emails = data.get('email', [])
        if not isinstance(emails, list):
            emails = [emails]

        apikeys = data.get('apikey', [])
        if not isinstance(apikeys, list):
            apikeys = [apikeys]

        title = data['title']
        body = data['body']
        url = data.get('url')
        channel = data.get('channel')

        for apikey in apikeys:
            if channel:
                self.send_push(apikey, title, body, url, channel, 'channel_tag')
            elif devices or emails:
                for device in devices:
                    self.send_push(apikey, title, body, url, device, 'device_iden')
                for email in emails:
                    self.send_push(apikey, title, body, url, email, 'email')
            else:
                self.send_push(apikey, title, body, url)

    def send_push(self, api_key, title, body, url=None, destination=None, destination_type=None):
        push_type = 'link' if url else 'note'
        data = {'type': push_type, 'title': title, 'body': body}
        if url:
            data['url'] = url
        if destination:
            data[destination_type] = destination

        # Make the request
        headers = {
            'Authorization': b'Basic ' + base64.b64encode(api_key.encode('ascii')),
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Flexget'
        }
        try:
            response = requests.post(PUSHBULLET_URL, headers=headers, json=data)
        except RequestException as e:
            if e.response.status_code == 429:
                reset_time = datetime.datetime.fromtimestamp(
                    int(e.response.headers['X-Ratelimit-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
                message = 'Monthly Pushbullet database operations  limit reached. Next reset: %s', reset_time
            else:
                message = 'Could not send notification to Pushbullet: %s', e.response.json()['error']['message']
            log.error(*message)
            return

        reset_time = datetime.datetime.fromtimestamp(
            int(response.headers['X-Ratelimit-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
        remaining = response.headers['X-Ratelimit-Remaining']
        log.verbose('Pushbullet notification sent. Database operations remaining until next reset: %s. '
                    'Next reset at: %s', remaining, reset_time)

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        # Send default values for backwards compatibility
        notify_config = {
            'to': [{'pushbullet': config}],
            'scope': 'entries',
            'what': 'accepted'
        }
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)


@event('plugin.register')
def register_plugin():
    plugin.register(PushbulletNotifier, 'pushbullet', api_ver=2, groups=['notifiers'])
