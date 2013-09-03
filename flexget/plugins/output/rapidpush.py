from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.utils import json
from flexget.plugin import register_plugin, priority
from flexget.utils.template import RenderError

log = logging.getLogger('rapidpush')

__version__ = 0.4
headers = {'User-Agent': "FlexGet RapidPush plugin/%s" % str(__version__)}
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

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='apikey', required=True)
        config.accept('list', key='apikey').accept('text')
        config.accept('text', key='category')
        config.accept('text', key='title')
        config.accept('text', key='group')
        config.accept('text', key='channel')
        config.accept('integer', key='priority')
        config.accept('text', key='message')
        config.accept('boolean', key='notify_accepted')
        config.accept('boolean', key='notify_rejected')
        config.accept('boolean', key='notify_failed')
        config.accept('boolean', key='notify_undecided')
        return config

    def prepare_config(self, config):
        config.setdefault('title', 'New release')
        config.setdefault('category', 'FlexGet')
        config.setdefault('priority', 2)
        config.setdefault('group', '')
        config.setdefault('channel', '')
        config.setdefault('message', '{{title}}')
        config.setdefault('notify_accepted', True)
        config.setdefault('notify_rejected', False)
        config.setdefault('notify_failed', False)
        config.setdefault('notify_undecided', False)
        return config

    # Run last to make sure other outputs are successful before sending notification
    @priority(0)
    def on_task_output(self, task, config):
        # get the parameters
        config = self.prepare_config(config)

        if config['notify_accepted']:
            log.info("Notify accepted entries")
            self.process_notifications(task, task.accepted, config)
        if config['notify_rejected']:
            log.info("Notify rejected entries")
            self.process_notifications(task, task.rejected, config)
        if config['notify_failed']:
            log.info("Notify failed entries")
            self.process_notifications(task, task.failed, config)
        if config['notify_undecided']:
            log.info("Notify undecided entries")
            self.process_notifications(task, task.undecided, config)

    # Process the given events.
    def process_notifications(self, task, entries, config):
        for entry in entries:
            if task.manager.options.test:
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

            response = task.requests.post(url, headers=headers, data=data, raise_status=False)

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

register_plugin(OutputRapidPush, 'rapidpush', api_ver=2)
