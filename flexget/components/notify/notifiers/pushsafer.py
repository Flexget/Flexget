from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

plugin_name = 'pushsafer'
log = logging.getLogger(plugin_name)

PUSHSAFER_URL = 'https://www.pushsafer.com/api'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('pushsafer.com', '5 seconds'))


class PushsaferNotifier(object):
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
                sound: <integer> (default is (none))
                vibration: <integer> (default is 0)
                timetolive: <integer> (default: (none))

    """

    schema = {
        'type': 'object',
        'properties': {
            'private_key': one_or_more({'type': 'string'}),
            'url': {'type': 'string'},
            'url_title': {'type': 'string'},
            'device': {'type': 'string'},
            'icon': {'type': 'integer', 'default': 1, 'maximum': 98, 'minimum': 1},
            'sound': {'type': 'integer', 'maximum': 28, 'minimum': 0},
            'vibration': {'type': 'integer', 'default': 0},
            'timetolive': {'type': 'integer', 'maximum': 43200, 'minimum': 0},
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
            'v': config.get('vibration'),
            'd': config.get('device'),
            'l': config.get('timetolive'),
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
