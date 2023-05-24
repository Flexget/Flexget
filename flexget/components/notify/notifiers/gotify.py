from http import HTTPStatus
from urllib.parse import urljoin

from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession

plugin_name = 'gotify'

requests = RequestSession(max_retries=3)


class GotifyNotifier:
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
            'url': {'format': 'url'},
            'token': {'type': 'string'},
            'priority': {'type': 'integer', 'default': 4},
            'content_type': {
                'type': 'string',
                'enum': ['text/plain', 'text/markdown'],
                'default': 'text/plain',
            },
        },
        'required': ['token', 'url'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send a Gotify notification
        """
        base_url = config['url']
        api_endpoint = '/message'
        url = urljoin(base_url, api_endpoint)
        params = {'token': config['token']}

        priority = config['priority']
        content_type = config['content_type']

        notification = {
            'title': title,
            'message': message,
            'priority': priority,
            'extras': {'client::display': {'contentType': content_type}},
        }
        # Make the request
        try:
            requests.post(url, params=params, json=notification)
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
