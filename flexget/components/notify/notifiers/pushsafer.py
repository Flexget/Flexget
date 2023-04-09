from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession
from flexget.utils.requests import TimedLimiter

plugin_name = 'pushsafer'
logger = logger.bind(name=plugin_name)

PUSHSAFER_URL = 'https://www.pushsafer.com/api'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('pushsafer.com', '5 seconds'))


class PushsaferNotifier:
    """
    Example::

      notify:
        entries:
          via:
            - pushsafer:
                private_key: <string> your private key (can also be a alias key) - Required
                url: <string> (default: '{{imdb_url}}')
                url_title: <string> (default: (none))
                device: <string> ypur device or device group id (default: (none))
                icon: <integer> (default is 1)
                iconcolor: <string> (default is (none))
                sound: <integer> (default is (none))
                vibration: <integer> (default is 0)
                timetolive: <integer> (default: (none))
                priority: <integer> (default: 0))
                retry: <integer> (default: (none)))
                expire: <integer> (default: (none)))
                confirm: <integer> (default: (none)))
                answer: <integer> (default: 0))
                answeroptions: <string> (default: (none)))
                answerforce: <integer> (default: 0))

    """

    schema = {
        'type': 'object',
        'properties': {
            'private_key': one_or_more({'type': 'string'}),
            'url': {'type': 'string'},
            'url_title': {'type': 'string'},
            'device': {'type': 'string'},
            'icon': {'type': 'integer', 'default': 1, 'maximum': 181, 'minimum': 1},
            'iconcolor': {'type': 'string'},
            'sound': {'type': 'integer', 'maximum': 62, 'minimum': 0},
            'vibration': {'type': 'integer', 'default': 0, 'maximum': 3, 'minimum': 0},
            'timetolive': {'type': 'integer', 'maximum': 43200, 'minimum': 0},
            'priority': {'type': 'integer', 'maximum': 2, 'minimum': -2},
            'retry': {'type': 'integer', 'maximum': 10800, 'minimum': 60},
            'expire': {'type': 'integer', 'maximum': 10800, 'minimum': 60},
            'confirm': {'type': 'integer', 'maximum': 10800, 'minimum': 10},
            'answer': {'type': 'integer', 'maximum': 1, 'minimum': 0},
            'answeroptions': {'type': 'string'},
            'answerforce': {'type': 'integer', 'maximum': 1, 'minimum': 0},
        },
        'required': ['private_key'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send a Pushsafer notification
        """
        notification = {
            't': title,
            'm': message,
            'ut': config.get('url_title'),
            'u': config.get('url'),
            's': config.get('sound'),
            'i': config.get('icon'),
            'c': config.get('iconcolor'),
            'v': config.get('vibration'),
            'd': config.get('device'),
            'l': config.get('timetolive'),
            'pr': config.get('priority'),
            're': config.get('retry'),
            'ex': config.get('expire'),
            'cr': config.get('confirm'),
            'a': config.get('answer'),
            'ao': config.get('answeroptions'),
            'af': config.get('answerforce'),
        }

        if not isinstance(config['private_key'], list):
            config['private_key'] = [config['private_key']]

        for key in config['private_key']:
            notification['k'] = key
            try:
                requests.post(PUSHSAFER_URL, data=notification)
            except RequestException as e:
                raise PluginWarning(repr(e))


@event('plugin.register')
def register_plugin():
    plugin.register(PushsaferNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
