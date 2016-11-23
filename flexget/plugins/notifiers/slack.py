from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from requests.exceptions import RequestException
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

__name__ = 'slack'

log = logging.getLogger(__name__)


class SlackNotifier(object):
    """
    Example:

      slack:
        webhook-url: <string>
        [text: <string>] (default: "{{task}} - Download started:
                                    {% if series_name is defined %}
                                    {{tvdb_series_name|d(series_name)}} {{series_id}} {{tvdb_ep_name|d('')}}
                                    {% elif imdb_name is defined %}
                                    {{imdb_name}} {{imdb_year}}
                                    {% else %}
                                    {{title}}
                                    {% endif %}"
        [channel: <string>] (override channel, use "@username" or "#channel")
        [username: <string>] (override username)
        [icon-emoji: <string>] (override emoji icon, do not include the colons:
                                e.g., use "tv" instead of ":tv:")

    Configuration parameters are also supported from entries (e.g., through set).
    """
    schema = {
        'type': 'object',
        'properties': {
            'webhook-url': {'type': 'string'},
            'message': {'type': 'string'},
            'channel': {'type': 'string'},
            'username': {'type': 'string'},
            'icon-emoji': {'type': 'string'},
            'template': {'type': 'string', 'format': 'template'},
        },
        'required': ['webhook-url'],
        'additionalProperties': False
    }

    def notify(self, data):
        url = data.pop('webhook-url')
        if data.get('icon-emoji'):
            data['icon-emoji'] = ":%s:" % data.get('icon-emoji')

        data['text'] = data.pop('message')
        try:
            requests.post(url, json=data)
        except RequestException as e:
            log.error('Slack notification failed: %s', e.args[0])
        else:
            log.verbose('Slack notification sent')

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
