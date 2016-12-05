from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from requests.exceptions import RequestException
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

__name__ = 'slack'

log = logging.getLogger(__name__)


class SlackNotifier(object):
    """
    Example:

      slack:
        web_hook_url: <string>
        [message: <string>]
        [channel: <string>] (override channel, use "@username" or "#channel")
        [username: <string>] (override username)
        [icon_emoji: <string>] (override emoji icon

    """
    schema = {
        'type': 'object',
        'properties': {
            'web_hook_url': {'type': 'string'},
            'message': {'type': 'string'},
            'channel': {'type': 'string'},
            'username': {'type': 'string'},
            'icon_emoji': {'type': 'string'},
            'file_template': {'type': 'string'},
        },
        'required': ['web_hook_url'],
        'additionalProperties': False
    }

    def notify(self, web_hook_url, message, channel=None, username=None, icon_emoji=None, **kwargs):
        """
        Send a Slack notification

        :param str web_hook_url: WebHook URL
        :param str message: Notification message
        :param str channel: Notification Channel
        :param str username: Notification username
        :param str icon_emoji: Notification icon_emoji
        """
        notification = {'text': message, 'channel': channel, 'username': username}
        if icon_emoji:
            notification['icon-emoji'] = ":%s:" % icon_emoji.strip(':')

        try:
            requests.post(web_hook_url, json=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])

    @plugin.priority(0)
    def on_task_output(self, task, config):
        # Send default values for backwards compatibility
        notify_config = {
            'to': [{__name__: config}],
            'scope': 'entries',
            'what': 'accepted'
        }
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)


@event('plugin.register')
def register_plugin():
    plugin.register(SlackNotifier, __name__, api_ver=2, groups=['notifiers'])
