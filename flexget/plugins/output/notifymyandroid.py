from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError

log = logging.getLogger('notifymyandroid')

url = 'https://www.notifymyandroid.com/publicapi/notify'


class OutputNotifyMyAndroid(object):
    """
    Example::

      notifymyandroid:
        apikey: xxxxxxx
        [application: application name, default FlexGet]
        [event: event title, default New Release]
        [priority: -2 - 2 (2 = highest), default 0]

    Configuration parameters are also supported from entries (eg. through set).
    """

    schema = {
        'type': 'object',
        'properties': {
            'apikey': {'type': 'string'},
            'application': {'type': 'string', 'default': 'FlexGet'},
            'event': {'type': 'string', 'default': 'New release'},
            'description': {'type': 'string', 'default': '{{title}}'},
            'priority': {'type': 'integer', 'default': 0}
        },
        'required': ['apikey'],
        'additionalProperties': False
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        for entry in task.accepted:

            if task.options.test:
                log.info("Would send notifymyandroid message about: %s", entry['title'])
                continue

            apikey = entry.get('apikey', config['apikey'])
            priority = entry.get('priority', config['priority'])
            application = entry.get('application', config['application'])
            try:
                application = entry.render(application)
            except RenderError as e:
                log.error('Error setting nma application: %s' % e)
            event = entry.get('event', config['event'])
            try:
                event = entry.render(event)
            except RenderError as e:
                log.error('Error setting nma event: %s' % e)
            description = config['description']
            try:
                description = entry.render(description)
            except RenderError as e:
                log.error('Error setting nma description: %s' % e)

            # Send the request
            data = {'priority': priority, 'application': application, 'apikey': apikey,
                    'event': event, 'description': description}
            response = task.requests.post(url, data=data, raise_status=False)

            # Check if it succeeded
            request_status = response.status_code

            # error codes and messages from http://nma.usk.bz/api.php
            if request_status == 200:
                log.debug("NotifyMyAndroid message sent")
            elif request_status == 400:
                log.error("Bad request, the parameters you provided did not validate")
            elif request_status == 401:
                log.error("Not authorized, the API key given is not valid, and does not correspond to a user.")
            elif request_status == 402:
                log.error("Not acceptable, your IP address has exceeded the API limit.")
            elif request_status == 500:
                log.error("Internal server error, something failed to execute properly on the NotifyMyAndroid side.")
            else:
                log.error("Unknown error when sending NotifyMyAndroid message")


@event('plugin.register')
def register_plugin():
    plugin.register(OutputNotifyMyAndroid, 'notifymyandroid', api_ver=2)
