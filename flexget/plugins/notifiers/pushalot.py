from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

log = logging.getLogger('pushalot')

PUSHALOT_URL = 'https://pushalot.com/api/sendmessage'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('pushalot.com', '5 seconds'))


class PushalotNotifier(object):
    """
    Example::

      pushalot:
        token: <string> Authorization token (can also be a list of tokens) - Required
        title: <string> (default: task name)
        body: <string> (default: '{{series_name}} {{series_id}}' )
        link: <string> (default: '{{imdb_url}}')
        linktitle: <string> (default: (none))
        important: <boolean> (default is False)
        silent: <boolean< (default is False)
        image: <string> (default: (none))
        source: <string> (default is 'FlexGet')
        timetolive: <integer>

    """
    default_body = ('{% if series_name is defined %}{{tvdb_series_name|d(series_name)}}' +
                    '{{series_id}} {{tvdb_ep_name|d('')}}{% elif imdb_name is defined %}' +
                    '{{imdb_name}} {{imdb_year}}{% else %}{{title}}{% endif %}')

    schema = {'type': 'object',
              'properties': {
                  'token': one_or_more({'type': 'string'}),
                  'title': {'type': 'string', 'default': 'Task {{task_name}}'},
                  'body': {'type': 'string', 'default': default_body},
                  'link': {'type': 'string', 'default': '{% if imdb_url is defined %}{{imdb_url}}{% endif %}'},
                  'linktitle': {'type': 'string', 'default': ''},
                  'important': {'type': 'boolean', 'default': False},
                  'silent': {'type': 'boolean', 'default': False},
                  'image': {'type': 'string', 'default': ''},
                  'source': {'type': 'string', 'default': 'FlexGet'},
                  'timetolive': {'type': 'integer', 'maximum': 43200, 'default': 0},
              },
              'required': ['token'],
              'additionalProperties': False}

    def notify(self, data):
        token = data.pop('token')
        if not isinstance(token, list):
            token = [token]

        for key in token:
            data['AuthorizationToken'] = key
            try:
                requests.post(PUSHALOT_URL, json=data)
            except RequestException as e:
                log.error('Pushalot notification failed: %s', e.response.json()['Description'])
            else:
                log.verbose('Pushalot notification sent')

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        # Send default values for backwards compatibility
        notify_config = {
            'to': [{'pushalot': config}],
            'scope': 'entries',
            'what': 'accepted'
        }
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)


@event('plugin.register')
def register_plugin():
    plugin.register(PushalotNotifier, 'pushalot', api_ver=2, groups=['notifiers'])
