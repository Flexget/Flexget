from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

plugin_name = 'pushalot'
log = logging.getLogger(plugin_name)

PUSHALOT_URL = 'https://pushalot.com/api/sendmessage'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('pushalot.com', '5 seconds'))


class PushalotNotifier(object):
    """
    Example::

      notify:
        entries:
          via:
            - pushalot:
                token: <string> Authorization token (can also be a list of tokens) - Required
                link: <string> (default: '{{imdb_url}}')
                linktitle: <string> (default: (none))
                important: <boolean> (default is False)
                silent: <boolean< (default is False)
                image: <string> (default: (none))
                source: <string> (default is 'FlexGet')
                timetolive: <integer>
    """
    schema = {'type': 'object',
              'properties': {
                  'api_key': one_or_more({'type': 'string'}),
                  'url': {'type': 'string'},
                  'url_title': {'type': 'string'},
                  'important': {'type': 'boolean', 'default': False},
                  'silent': {'type': 'boolean', 'default': False},
                  'image': {'type': 'string'},
                  'source': {'type': 'string', 'default': 'FlexGet'},
                  'timetolive': {'type': 'integer', 'maximum': 43200, 'minimum': 0},
              },
              'required': ['api_key'],
              'additionalProperties': False}

    def notify(self, title, message, config):
        """
        Send a Pushalot notification
        """
        notification = {'Title': title, 'Body': message, 'LinkTitle': config.get('url_title'),
                        'Link': config.get('url'), 'IsImportant': config.get('important'),
                        'IsSilent': config.get('silent'), 'Image': config.get('image'), 'Source': config.get('source'),
                        'TimeToLive': config.get('timetolive')}

        if not isinstance(config['api_key'], list):
            config['api_key'] = [config['api_key']]

        for key in config['api_key']:
            notification['AuthorizationToken'] = key
            try:
                requests.post(PUSHALOT_URL, json=notification)
            except RequestException as e:
                raise PluginWarning(repr(e))


@event('plugin.register')
def register_plugin():
    plugin.register(PushalotNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
