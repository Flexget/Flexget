from builtins import *

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from requests.exceptions import RequestException
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

__name__ = 'microsoftteams'

log = logging.getLogger(__name__)

class TeamsNotifier(object):
    """
    Example:

      teams:
        web_hook_url: <string>
        [message: <string>]
        [title: <string>]
        [themecolor: <string>]
    """
    schema = {
        'type': 'object',
        'properties': {
            'web_hook_url': {'type': 'string'},
            'message': {'type': 'string'},
            'title': {'type': 'string'},
            'themecolor': {'type': 'string'},
        },
        'required': ['web_hook_url', 'message'],
        'additionalProperties': False
    }

    def notify(self, web_hook_url, message, config, title=None, themecolor=None):
        """
        Send notification to Microsoft Teams

        :param str web_hook_url: WebHook Url
        :param str message: Notification message
        :param str title: Message title
        :return:
        """

        notification = {'text': message, 'title': title, 'themecolor': themecolor}

        try:
            requests.post(config['web_hook_url'], json=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])

@event('plugin.register')
def register_plugin():
    plugin.register(TeamsNotifier, __name__, api_ver=2, groups=['notifiers'])