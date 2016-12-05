from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

__name__ = 'pushalot'
log = logging.getLogger(__name__)

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
    schema = {'type': 'object',
              'properties': {
                  'api_key': one_or_more({'type': 'string'}),
                  'title': {'type': 'string'},
                  'message': {'type': 'string'},
                  'url': {'type': 'string'},
                  'url_title': {'type': 'string'},
                  'important': {'type': 'boolean', 'default': False},
                  'silent': {'type': 'boolean', 'default': False},
                  'image': {'type': 'string'},
                  'source': {'type': 'string', 'default': 'FlexGet'},
                  'timetolive': {'type': 'integer', 'maximum': 43200, 'minimum': 0},
                  'file_template': {'type': 'string'},
              },
              'required': ['api_key'],
              'additionalProperties': False}

    def notify(self, api_key, message, title, url=None, url_title=None, important=None, silent=None, image=None,
               source=None, timetolive=None, **kwargs):
        """
        Send a Pushalot notification

        :param str api_key: one or more API keys
        :param str message: Notification message
        :param str title: Notification title
        :param str url: Enclosed url link
        :param str url_title: Title for enclosed link in the Link field
        :param bool important: Indicator whether the message should be visually marked as important within client app
        :param bool silent: If set to True will prevent sending toast notifications to connected devices, resulting in
            silent delivery
        :param str image: Image thumbnail URL link
        :param str source: Notification source name that will be displayed instead of authorization token's app name.
        :param int timetolive: Time in minutes after which message automatically gets purged
        """
        notification = {'Title': title, 'Body': message, 'LinkTitle': url_title, 'Link': url, 'IsImportant': important,
                        'IsSilent': silent, 'Image': image, 'Source': source, 'TimeToLive': timetolive}

        if not isinstance(api_key, list):
            api_key = [api_key]

        for key in api_key:
            notification['AuthorizationToken'] = key
            try:
                requests.post(PUSHALOT_URL, json=notification)
            except RequestException as e:
                raise PluginWarning(repr(e))

    # Run last to make sure other outputs are successful before sending notification
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
    plugin.register(PushalotNotifier, __name__, api_ver=2, groups=['notifiers'])
