import logging
import base64
import datetime
import re

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException
from http import HTTPStatus

plugin_name = 'gotify'
log = logging.getLogger(plugin_name)

requests = RequestSession(max_retries=3)

gotify_url_pattern = {
    'type': 'string',
    'pattern': r'^http(s?)\:\/\/.*\/message$',
    'error_pattern': 'Gotify URL must begin with http(s) and end with `/message`',
}

class GotifyNotifier(object):
    """
    Example::

    notify:
      entries:
        via:
          - gotify:
              url: <GOTIFY_SERVER_URL>
              token: <GOTIFY_TOKEN>
              priority: <PRIORITY>
    Configuration parameters are also supported from entries (eg. through set).
    """
    schema = {
        'type': 'object',
        'properties': {
            'url': gotify_url_pattern,
            'token': {'type': 'string'},
            'priority': {'type': 'integer', 'default': 4},  
        },  
        'required': [
            'token',
            'url',
        ],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send a Gotify notification
        """
        url = config['url']
        params = {'token': config['token']}
        
        priority = config['priority']
        
        notification = {'title': title, 'message': message, 'priority': priority}
        # Make the request
        try:
            response = requests.post(url, params=params, json=notification)
        except RequestException as e:
            if e.response is not None:
                if e.response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    message = 'Invalid Gotify access token'
                else:
                  message = e.response.json()['error']['message']
            else:
                message = str(e)
            raise PluginWarning(message)

@event('plugin.register')
def register_plugin():
    plugin.register(GotifyNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
