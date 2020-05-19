from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

plugin_name = 'ms_teams'

logger = logger.bind(name=plugin_name)


class MsTeamsNotifier:
    """
    Example::

      notify:
        entries:
          via:
            ms_teams:
              web_hook_url: <string>
              [message: <string>]
              [title: <string>]
              [theme_color: <string>]
    """

    schema = {
        'type': 'object',
        'properties': {
            'web_hook_url': {'type': 'string'},
            'title': {'type': 'string'},
            'theme_color': {'type': 'string'},
        },
        'required': ['web_hook_url'],
        'additionalProperties': False,
    }

    def notify(self, web_hook_url, message, config, title=None, themecolor=None):
        """
        Send notification to Microsoft Teams
        """
        notification = {'text': message, 'title': title, 'theme_color': themecolor}

        try:
            requests.post(config['web_hook_url'], json=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])


@event('plugin.register')
def register_plugin():
    plugin.register(MsTeamsNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
