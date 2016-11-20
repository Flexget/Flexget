from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

log = logging.getLogger('rapidpush')

RAPIDPUSH_URL = 'https://rapidpush.net/api'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('rapidpush.net', '5 seconds'))


class RapidpushNotifer(object):
    """
    Example::

      rapidpush:
        apikey: xxxxxxx (can also be a list of api keys)
        [category: category, default FlexGet]
        [title: title, default New release]
        [group: device group, default no group]
        [message: the message, default {{title}}]
        [channel: the broadcast notification channel, if provided it will be send to the channel subscribers instead of
            your devices, default no channel]
        [priority: 0 - 6 (6 = highest), default 2 (normal)]
        [notify_accepted: boolean true or false, default true]
        [notify_rejected: boolean true or false, default false]
        [notify_failed: boolean true or false, default false]
        [notify_undecided: boolean true or false, default false]

    """
    schema = {
        'type': 'object',
        'properties': {
            'apikey': one_or_more({'type': 'string'}),
            'category': {'type': 'string', 'default': 'Flexget'},
            'title': {'type': 'string', 'default': 'New Release'},
            'group': {'type': 'string'},
            'channel': {'type': 'string'},
            'priority': {'type': 'integer', 'minimum': 0, 'maximum': 6},
            'message': {'type': 'string', 'default': '{{title}}'},
            'notify_accepted': {'type': 'boolean', 'default': True},
            'notify_rejected': {'type': 'boolean', 'default': False},
            'notify_failed': {'type': 'boolean', 'default': False},
            'notify_undecided': {'type': 'boolean', 'default': False}
        },
        'additionalProperties': False,
        'required': ['apikey']
    }

    def notify(self, data):
        apikey = data['apikey']
        if not isinstance(apikey, list):
            apikey = [apikey]

        title = data['title']
        message = data['message']

        wrapper = {}
        message_data = {'title': title, 'message': message}

        channel = data.get('channel')
        if channel:
            wrapper['command'] = 'broadcast'
        else:
            wrapper['command'] = 'notify'
            message_data['category'] = data['category']
            if data.get('group'):
                message_data['group'] = data.get('group')
            if data.get('priority'):
                message_data['priority'] = data.get('priority')

        wrapper['data'] = message_data
        for key in apikey:
            wrapper['apikey'] = key
            try:
                response = requests.post(RAPIDPUSH_URL, json=wrapper)
            except RequestException as e:
                log.error('Rapidpush notification failed: %s', e.args[0])
            else:
                code = response.json()['code']
                if code > 400:
                    log.error('Rapidpush notification failed: %s. Additional data: %s'
                              , response.json()['desc'], response.json()['data'])
                else:
                    log.verbose('Rapidpush notification successfully sent')

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        what = []
        if config['notify_accepted']:
            what.append('accepted')
        if config['notify_rejected']:
            what.append('rejected')
        if config['notify_failed']:
            what.append('failed')
        if config['notify_undecided']:
            what.append('undecided')

        notify_config = {
            'to': [{'rapidpush': config}],
            'scope': 'entries',
            'what': what
        }
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)


@event('plugin.register')
def register_plugin():
    plugin.register(RapidpushNotifer, 'rapidpush', api_ver=2, groups=['notifiers'])
