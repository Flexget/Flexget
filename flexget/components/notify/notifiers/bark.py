from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

plugin_name = 'bark'

logger = logger.bind(name=plugin_name)


class BarkNotifier:
    """
    Example::

      notify:
        entries:
        title: |
              {{task}}
        message: |
              {% if series_name is defined %}{{series_name}}{% if series_id is defined %} - {{series_id}}{% endif %}{% if trakt_ep_name is defined %} - {{trakt_ep_name}}{% endif %}
              {% elif imdb_name is defined%}{{movie_name}}
              {% else %}{{title}}
              {% endif %}
          via:
            webpost:
              server: <string>
              device_key: <string>
              options:
                key: value
              # https://github.com/Finb/bark-server/blob/master/docs/API_V2.md

    """

    schema = {
        'type': 'object',
        'properties': {
            'server': {'type': 'string'},
            'device_key': {'type': 'string'},
            'options': {
                'type': 'object',
                'additionalProperties': {
                    'oneOf': [{'type': 'string'}, {'type': 'integer'}]
                },
            },
        },
        'required': ['server', 'device_key'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send notification to Bark
        """
        notification = {
            'title': title,
            'body': message,
        }
        server = config.get('server')
        notification['device_key'] = config.get('device_key')
        notification.update(config.get('options', {}))
        try:
            requests.post(server, json=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])


@event('plugin.register')
def register_plugin():
    plugin.register(BarkNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
