from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import base64
import datetime

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

plugin_name = 'gotify'
log = logging.getLogger(plugin_name)

requests = RequestSession(max_retries=3)

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
                'oneOf': [
                    {'url': {'type': 'string', 'format': 'url'}},
                    {'token': {'type': 'string'}},
                    {'priority': {'type': 'integer', 'default': 4}},
                ],  
            },
          'required': [
              'token',
              'url',
          ],
        'error_oneOf': 'One (and only one) of `url` or `priority` are allowed.',
        'additionalProperties': False,
      }

    def notify(self, title, message, config):
        """
        Send a Gotify notification
        """
        priority = config.get('priority')      
        token = config.get('token')
        url = config.get('url') + '?token=' + token
        self.send_push(token, title, message, priority, url)

    def send_push(self, token, title, body, priority, url=None, destination=None, destination_type=None):

        requests = RequestSession(max_retries=3)
        notification = {'title': title, 'message': body, 'priority': priority}
        if url:
            notification['url'] = url + '?token=' + token
        if destination:
            notification[destination_type] = destination

        # Make the request
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Flexget',
        }
        try:
            response = requests.post(url, headers=headers, json=notification)
        except RequestException as e:
            if e.response is not None:
                if e.response.status_code == 401 or e.response.status_code == 403:
                    message = 'Invalid Gotify access token'
                elif e.response.status_code == 404:
                    url_format = 'https://push.example.com/message'
                    message = (
                        'Invalid Gotify URL, please verify that the URL matches the format: %s'
                        % url_format
                    )
                else:
                  message = e.response.json()['error']['message']
            else:
                message = str(e)
            raise PluginWarning(message)

@event('plugin.register')
def register_plugin():
    plugin.register(GotifyNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
