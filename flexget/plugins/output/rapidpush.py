from __future__ import unicode_literals, division, absolute_import
import logging
import json
from flexget.plugin import register_plugin
from flexget.utils.template import RenderError

log = logging.getLogger('rapidpush')

__version__ = 0.1
headers = {'User-Agent': "FlexGet RapidPush plugin/%s" % str(__version__)}
url = 'https://rapidpush.net/api'


class OutputRapidPush(object):
    """
    Example::

      rapidpush:
        apikey: xxxxxxx
        [category: category, default FlexGet]
        [title: title, default New release]
        [group: device group, default no group]
        [message: the message, to include the title from flexget insert {{title}} at the wanted position, default {{title}}]
        [priority: 0 - 6 (6 = highest), default 2 (normal)]

    Configuration parameters are also supported from entries (eg. through set).
    """

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='apikey', required=True)
        config.accept('text', key='category')
        config.accept('text', key='title')
        config.accept('text', key='group')
        config.accept('integer', key='priority')
        config.accept('text', key='message')
        return config

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}	
        config.setdefault('title', 'New release')
        config.setdefault('category', 'FlexGet')
        config.setdefault('priority', 2)
        config.setdefault('group', '')
        config.setdefault('message', '{{title}}')
        return config

    def on_task_output(self, task, config):
        # get the parameters
        config = self.prepare_config(config)
        log.info("Get all accepted entries")
        for entry in task.accepted:

            if task.manager.options.test:
                log.info("Would send RapidPush notification about: %s", entry['title'])
                continue

            log.info("Send RapidPush notification about: %s", entry['title'])
            apikey = entry.get('apikey', config['apikey'])
            priority = entry.get('priority', config['priority'])

            category = entry.get('category', config['category'])
            try:
                category = entry.render(category)
            except RenderError as e:
                log.error('Error setting RapidPush category: %s' % e)

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
            data = {'apikey': apikey, 'command': 'notify', 'header_errors': '1', 'data': data_string}
            response = task.requests.post(url, headers=headers, data=data, raise_status=False)

            # Check if it succeeded
            request_status = response.status_code

            # error codes and messages are explained at: https://rapidpush.net/developer-info.html
            if request_status == 200:
                log.debug("RapidPush message sent")
            elif request_status == 405:
                log.error("invalid parameter")
            elif request_status == 407:
                log.error("Could not insert notification, internal error")
            elif request_status == 408:
                log.error("Invalid API-Key.")
            elif request_status == 409:
                log.error("Invalid command")
            elif request_status == 410:
                log.error("API rate limit exceeded")
            else:
                log.error("Unknown error while sending RapidPush notification")

register_plugin(OutputRapidPush, 'rapidpush', api_ver=2)
