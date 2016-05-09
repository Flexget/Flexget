from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError
from requests import ConnectionError

log = logging.getLogger('slack')


class OutputSlack(object):
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
    default_body = ('{{task}} - Download started: '
                    '{% if series_name is defined %}'
                    '{{tvdb_series_name|d(series_name)}} {{series_id}} {{tvdb_ep_name|d('')}}'
                    '{% elif imdb_name is defined %}'
                    '{{imdb_name}} {{imdb_year}}'
                    '{% else %}'
                    '{{title}}'
                    '{% endif %}')
    schema = {
        'type': 'object',
        'properties': {
            'webhook-url': {'type': 'string'},
            'text': {'type': 'string', 'default': default_body},
            'channel': {'type': 'string'},
            'username': {'type': 'string'},
            'icon-emoji': {'type': 'string'},
        },
        'required': ['webhook-url'],
        'additionalProperties': False
    }

    @plugin.priority(0)
    def on_task_output(self, task, config):

        for entry in task.accepted:
            webhook_url = config.get('webhook-url')
            text = config.get('text')
            channel = config.get('channel')
            username = config.get('username')
            icon_emoji = config.get('icon-emoji')

            if icon_emoji:
                icon_emoji = ":%s:" % icon_emoji

            try:
                text = entry.render(text)
            except RenderError as e:
                log.warning('Problem rendering `text`: %s' % e)
                text = 'Download started'

            self.send_post(task, webhook_url, text, channel, username,
                           icon_emoji)

    def send_post(self, task, webhook_url, text, channel, username,
                  icon_emoji):

        data = {'text': text}
        if channel:
            data['channel'] = channel
        if username:
            data['username'] = username
        if icon_emoji:
            data['icon_emoji'] = icon_emoji

        if task.options.test:
            log.info('Test mode. Slack notification would be:')
            log.info('    Webhook URL: {0}'.format(webhook_url))
            log.info('    Text: {0}'.format(text))
            if channel:
                log.info('    Channel: {0}'.format(channel))
            if username:
                log.info('    Username: {0}'.format(username))
            if icon_emoji:
                log.info('    Icon Emoji: :{0}:'.format(icon_emoji))
            log.info('    Raw POST Data: {0}'.format(json.dumps(data)))
            # Early return (test mode)
            return

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Flexget'
        }
        try:
            response = task.requests.post(webhook_url, headers=headers,
                                          data=json.dumps(data),
                                          raise_status=False)
        except ConnectionError as e:
            log.error('Unable to connect to Slack API: {0}'.format(e.message))
            return

        response_code = response.status_code

        if response_code == 200:
            log.debug('Slack notification sent')
        elif response_code == 500:
            log.warning('Slack notification failed: server problem')
        elif response_code >= 400:
            log.error('Slack API error {0}: {1}'.format(response_code, response.content))
        else:
            log.error('Unknown error when sending Slack notification: {0}'.format(response_code))


@event('plugin.register')
def register_plugin():
    plugin.register(OutputSlack, 'slack', api_ver=2)
