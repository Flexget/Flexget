from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError
from flexget.config_schema import one_or_more

log = logging.getLogger('rapidpush')

url = 'https://rapidpush.net/api'


class OutputRapidPush(object):
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

    Configuration parameters are also supported from entries (eg. through set).
    """
    schema = {
        'type': 'object',
        'properties': {
            'apikey': one_or_more({'type': 'string'}),
            'category': {'type': 'string', 'default': 'Flexget'},
            'title': {'type': 'string', 'default': 'New Release'},
            'group': {'type': 'string', 'default': ''},
            'channel': {'type': 'string', 'default': ''},
            'priority': {'type': 'integer', 'default': 2},
            'message': {'type': 'string', 'default': '{{title}}'},
            'notify_accepted': {'type': 'boolean', 'default': True},
            'notify_rejected': {'type': 'boolean', 'default': False},
            'notify_failed': {'type': 'boolean', 'default': False},
            'notify_undecided': {'type': 'boolean', 'default': False}
        },
        'additionalProperties': False,
        'required': ['apikey']
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        # get the parameters

        if config['notify_accepted']:
            log.debug("Notify accepted entries")
            self.process_notifications(task, task.accepted, config)
        if config['notify_rejected']:
            log.debug("Notify rejected entries")
            self.process_notifications(task, task.rejected, config)
        if config['notify_failed']:
            log.debug("Notify failed entries")
            self.process_notifications(task, task.failed, config)
        if config['notify_undecided']:
            log.debug("Notify undecided entries")
            self.process_notifications(task, task.undecided, config)

    # Process the given events.
    def process_notifications(self, task, entries, config):
        for entry in entries:
            if task.options.test:
                log.info("Would send RapidPush notification about: %s", entry['title'])
                continue

            log.info("Send RapidPush notification about: %s", entry['title'])
            apikey = entry.get('apikey', config['apikey'])
            if isinstance(apikey, list):
                apikey = ','.join(apikey)

            title = config['title']
            try:
                title = entry.render(title)
            except RenderError as e:
                log.error('Error setting RapidPush title: %s' % e)

            message = config['message']
            try:
                message = entry.render(message)
            except RenderError as e:
                log.error('Error setting RapidPush message: %s' % e)

            # Check if we have to send a normal or a broadcast notification.
            if not config['channel']:
                priority = entry.get('priority', config['priority'])

                category = entry.get('category', config['category'])
                try:
                    category = entry.render(category)
                except RenderError as e:
                    log.error('Error setting RapidPush category: %s' % e)

                group = entry.get('group', config['group'])
                try:
                    group = entry.render(group)
                except RenderError as e:
                    log.error('Error setting RapidPush group: %s' % e)

                # Send the request
                data_string = json.dumps({
                    'title': title,
                    'message': message,
                    'priority': priority,
                    'category': category,
                    'group': group})
                data = {'apikey': apikey, 'command': 'notify', 'data': data_string}
            else:
                channel = config['channel']
                try:
                    channel = entry.render(channel)
                except RenderError as e:
                    log.error('Error setting RapidPush channel: %s' % e)

                # Send the broadcast request
                data_string = json.dumps({
                    'title': title,
                    'message': message,
                    'channel': channel})
                data = {'apikey': apikey, 'command': 'broadcast', 'data': data_string}

            try:
                response = task.requests.post(url, data=data, raise_status=False)
            except RequestException as e:
                log.error('Error sending data to rapidpush: %s' % e)
                continue

            json_data = response.json()
            if 'code' in json_data:
                if json_data['code'] == 200:
                    log.debug("RapidPush message sent")
                else:
                    log.error(json_data['desc'] + " (" + str(json_data['code']) + ")")
            else:
                for item in json_data:
                    if json_data[item]['code'] == 200:
                        log.debug(item + ": RapidPush message sent")
                    else:
                        log.error(item + ": " + json_data[item]['desc'] + " (" + str(json_data[item]['code']) + ")")


@event('plugin.register')
def register_plugin():
    plugin.register(OutputRapidPush, 'rapidpush', api_ver=2)
