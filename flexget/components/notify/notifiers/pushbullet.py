import base64
import datetime

from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession
from flexget.utils.requests import TimedLimiter

plugin_name = 'pushbullet'
logger = logger.bind(name=plugin_name)

PUSHBULLET_URL = 'https://api.pushbullet.com/v2/pushes'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('pushbullet.com', '5 seconds'))


class PushbulletNotifier:
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

    @staticmethod
    def send_push(api_key, title, body, url=None, destination=None, destination_type=None):
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
                    reset_time = e.response.headers.get('X-Ratelimit-Reset')
                    if reset_time:
                        reset_time = datetime.datetime.fromtimestamp(int(reset_time)).strftime(
                            '%Y-%m-%d %H:%M:%S'
                        )
                        message = f'Monthly Pushbullet database operations limit reached. Next reset: {reset_time}'
                else:
                    message = e.response.json()['error']['message']
            else:
                message = str(e)
            raise PluginWarning(message)

        reset_time = response.headers.get('X-Ratelimit-Reset')
        remaining = response.headers.get('X-Ratelimit-Remaining')
        if reset_time and remaining:
            reset_time = datetime.datetime.fromtimestamp(int(reset_time))
            logger.debug(
                'Pushbullet notification sent. Database operations remaining until next reset: {}. '
                'Next reset at: {}',
                remaining,
                reset_time,
            )


@event('plugin.register')
def register_plugin():
    plugin.register(PushbulletNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
