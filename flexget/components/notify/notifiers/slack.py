from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from requests.exceptions import RequestException
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

plugin_name = 'slack'

log = logging.getLogger(plugin_name)


class SlackNotifier(object):
    """
    Example:

      notify:
        entries:
          via:
            - slack:
                web_hook_url: <string>
                [channel: <string>] (override channel, use "@username" or "#channel")
                [username: <string>] (override username)
                [icon_emoji: <string>] (override emoji icon)
                [icon_url: <string>] (override emoji icon)
                [attachments: <array>[<object>]] (override attachments)

    """
    schema = {
        'type': 'object',
        'properties': {
            'web_hook_url': {'type': 'string', 'format': 'uri'},
            'username': {'type': 'string', 'default': 'Flexget'},
            'icon_url': {'type': 'string', 'format': 'uri'},
            'icon_emoji': {'type': 'string'},
            'channel': {'type': 'string'},
            'unfurl_links': {'type': 'boolean'},
            'message': {'type': 'string'},
            'attachments': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'author_name': {'type': 'string'},
                        'author_link': {'type': 'string'},
                        'author_icon': {'type': 'string'},
                        'title_link': {'type': 'string'},
                        'image_url': {'type': 'string'},
                        'thumb_url': {'type': 'string'},
                        'footer': {'type': 'string'},
                        'footer_icon': {'type': 'string'},
                        'ts': {'type': 'number'},
                        'fallback': {'type': 'string'},
                        'text': {'type': 'string'},
                        'pretext': {'type': 'string'},
                        'color': {'type': 'string'},
                        'fields': {
                            'type': 'array',
                            'minItems': 1,
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'title': {'type': 'string'},
                                    'value': {'type': 'string'},
                                    'short': {'type': 'boolean'}
                                },
                                'required': ['title'],
                                'additionalProperties': False
                            }
                        }
                    },
                    'required': ['fallback'],
                    'additionalProperties': False
                }
            }
        },
        'not': {
            'required': ['icon_emoji', 'icon_url']
        },
        'error_not': 'Can only use one of \'icon_emoji\' or \'icon_url\'',
        'required': ['web_hook_url'],
        'additionalProperties': False
    }

    def notify(self, title, message, config):
        """
        Send a Slack notification
        """
        notification = {
            'text': message,
            'username': config.get('username'),
            'channel': config.get('channel'),
            'attachments': config.get('attachments')
        }
        if config.get('icon_emoji'):
            notification['icon_emoji'] = ':%s:' % config['icon_emoji'].strip(':')
        if config.get('icon_url'):
            notification['icon_url'] = config['icon_url']

        try:
            requests.post(config['web_hook_url'], json=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])


@event('plugin.register')
def register_plugin():
    plugin.register(SlackNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
