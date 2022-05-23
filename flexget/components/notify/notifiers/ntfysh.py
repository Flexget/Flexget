from http import HTTPStatus
from urllib.parse import urljoin

from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession

plugin_name = 'ntfysh'

requests = RequestSession(max_retries=3)


class NtfyshNotifier(object):
    """
    Example::

    notify:
      entries:
        via:
          - ntfysh:
              topic: <NTFY_TOPIC>

    Configuration parameters are also supported from entries (eg. through set).
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'format': 'url', 'default': 'https://ntfy.sh/'},
            'topic': {'type': 'string'},
            'priority': {'type': 'integer', 'default': 3},
            'delay': {'type': 'string'},
            'tags': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
        },
        'required': ['topic', 'url'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send a Ntfy.sh notification
        """
        base_url = config['url']
        topic = config['topic']
        url = urljoin(base_url, topic)

        req = {
            'url': url,
            'data': message,
            'params': {'title': title, 'priority': config['priority']},
        }

        if 'username' in config or 'password' in config:
            req['auth'] = HTTPBasicAuth(config.get('username', ''), config.get('password', ''))

        if 'delay' in config:
            req['params']['delay'] = config['delay']
        if 'tags' in config:
            req['params']['tags'] = config['tags']

        try:
            response = requests.post(**req)
        except RequestException as e:
            if e.response is not None:
                if e.response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    message = 'Invalid username and password'
                else:
                    message = e.response.text()
            else:
                message = str(e)
            raise PluginWarning(message)


@event('plugin.register')
def register_plugin():
    plugin.register(NtfyshNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
