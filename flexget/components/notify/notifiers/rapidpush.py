import json

from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession
from flexget.utils.requests import TimedLimiter

plugin_name = 'rapidpush'
logger = logger.bind(name=plugin_name)

RAPIDPUSH_URL = 'https://rapidpush.net/api'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('rapidpush.net', '5 seconds'))


class RapidpushNotifier:
    """
    Example::

      notify:
        entries:
          via:
            - rapidpush:
                apikey: xxxxxxx (can also be a list of api keys)
                [category: category, default FlexGet]
                [group: device group, default no group]
                [channel: the broadcast notif. channel; if provided it will be send to the channel subscribers instead of
                    your devices, default no channel]
                [priority: 0 - 6 (6 = highest), default 2 (normal)]
    """

    schema = {
        'type': 'object',
        'properties': {
            'api_key': one_or_more({'type': 'string'}),
            'category': {'type': 'string', 'default': 'Flexget'},
            'group': {'type': 'string'},
            'channel': {'type': 'string'},
            'priority': {'type': 'integer', 'minimum': 0, 'maximum': 6},
        },
        'additionalProperties': False,
        'required': ['api_key'],
        'not': {
            'anyOf': [
                {'required': ['channel', 'group']},
                {'required': ['channel', 'category']},
                {'required': ['channel', 'priority']},
            ]
        },
        'error_not': 'Cannot use \'channel\' with \'group\', \'category\' or \'priority\'',
    }

    def notify(self, title, message, config):
        """
        Send a Rapidpush notification
        """
        notification = {'title': title, 'message': message}
        if not isinstance(config['api_key'], list):
            config['api_key'] = [config['api_key']]

        if config.get('channel'):
            params = {'command': 'broadcast'}
            notification['channel'] = config['channel']
        else:
            params = {'command': 'notify'}
            notification['category'] = config['category']
            if config.get('group'):
                notification['group'] = config['group']
            if config.get('priority') is not None:
                notification['priority'] = config['priority']

        params['data'] = json.dumps(notification)
        for key in config['api_key']:
            params['apikey'] = key
            try:
                response = requests.post(RAPIDPUSH_URL, params=params)
            except RequestException as e:
                raise PluginWarning(e.args[0])
            else:
                if response.json()['code'] > 400:
                    raise PluginWarning(response.json()['desc'])


@event('plugin.register')
def register_plugin():
    plugin.register(RapidpushNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
