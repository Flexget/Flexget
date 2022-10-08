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
              [level: <string>]
              [badge: <integer>]
              [automaticallyCopy: <string>]
              [copy: <string>]
              [sound: <string>]
              [icon: <string>]
              [group: <string>]
              [isArchive: <string>]
              [url: <string>]

    # https://github.com/Finb/bark-server/blob/master/docs/API_V2.md

    """

    schema = {
        'type': 'object',
        'properties': {
            'server': {'type': 'string'},
            'device_key': {'type': 'string'},
            'level': {'type': 'string'},
            'badge': {'type': 'integer'},
            'automaticallyCopy': {'type': 'string'},
            'copy': {'type': 'string'},
            'sound': {'type': 'string'},
            'icon': {'type': 'string'},
            'group': {'type': 'string'},
            'isArchive': {'type': 'string'},
            'url': {'type': 'string'},
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
        options = config.copy()
        server = options.pop('server')
        notification.update(options)
        try:
            requests.post(server, json=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])


@event('plugin.register')
def register_plugin():
    plugin.register(BarkNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
