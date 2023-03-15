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
              [automatically_copy: <boolean>]
              [copy: <string>]
              [sound: <string>]
              [icon: <string>]
              [group: <string>]
              [is_archive: <boolean>]
              [url: <string>]

    # https://github.com/Finb/bark-server/blob/master/docs/API_V2.md

    """

    schema = {
        'type': 'object',
        'properties': {
            'server': {'type': 'string'},
            'device_key': {'type': 'string'},
            'level': {'type': 'string', 'enum': ['active', 'timeSensitive', 'passive']},
            'badge': {'type': 'integer'},
            'automatically_copy': {'type': 'boolean'},
            'copy': {'type': 'string'},
            'sound': {'type': 'string'},
            'icon': {'type': 'string'},
            'group': {'type': 'string'},
            'is_archive': {'type': 'boolean'},
            'url': {'type': 'string'},
        },
        'required': ['server', 'device_key'],
        'additionalProperties': False,
    }

    def prepare_config(self, config):
        options = config.copy()
        server = options.pop('server')
        if options.pop('automatically_copy', False):
            options['automaticallyCopy'] = '1'
        if options.pop('is_archive', False):
            options['isArchive'] = '1'
        return server, options

    def notify(self, title, message, config):
        """
        Send notification to Bark
        """
        notification = {
            'title': title,
            'body': message,
        }
        server, options = self.prepare_config(config)
        notification.update(options)
        try:
            requests.post(server, json=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])


@event('plugin.register')
def register_plugin():
    plugin.register(BarkNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
