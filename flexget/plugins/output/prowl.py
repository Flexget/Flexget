from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError

log = logging.getLogger('prowl')


class OutputProwl(object):
    """
    Send prowl notifications

    Example::

      prowl:
        apikey: xxxxxxx
        [application: application name, default FlexGet]
        [event: event title, default New Release]
        [priority: -2 - 2 (2 = highest), default 0]
        [description: notification to send]

    Configuration parameters are also supported from entries (eg. through set).
    """
    schema = {
        'type': 'object',
        'properties': {
            'apikey': {'type': 'string'},
            'application': {'type': 'string', 'default': 'FlexGet'},
            'event': {'type': 'string', 'default': 'New Release'},
            'priority': {'type': 'integer', 'default': 0},
            'description': {'type': 'string'}
        },
        'required': ['apikey'],
        'additionalProperties': False
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        for entry in task.accepted:

            # get the parameters
            apikey = entry.get('apikey', config['apikey'])
            application = entry.get('application', config['application'])
            event = entry.get('event', config['event'])
            priority = entry.get('priority', config['priority'])
            description = config.get('description', entry['title'])

            # If event has jinja template, render it
            try:
                event = entry.render(event)
            except RenderError as e:
                log.error('Error rendering jinja event: %s' % e)

            # If description has jinja template, render it
            try:
                description = entry.render(description)
            except RenderError as e:
                description = entry['title']
                log.error('Error rendering jinja description: %s' % e)

            url = 'https://api.prowlapp.com/publicapi/add'
            data = {'priority': priority, 'application': application, 'apikey': apikey,
                    'event': event.encode('utf-8'), 'description': description}

            if task.options.test:
                log.info('Would send prowl message about: %s', entry['title'])
                log.debug('options: %s' % data)
                continue

            try:
                response = task.requests.post(url, data=data, raise_status=False)
            except RequestException as e:
                log.error('Error with request: %s' % e)
                continue

            # Check if it succeeded
            request_status = response.status_code

            # error codes and messages from http://prowl.weks.net/api.php
            if request_status == 200:
                log.debug("Prowl message sent")
            elif request_status == 400:
                log.error("Bad request, the parameters you provided did not validate")
            elif request_status == 401:
                log.error("Not authorized, the API key given is not valid, and does not correspond to a user.")
            elif request_status == 406:
                log.error("Not acceptable, your IP address has exceeded the API limit.")
            elif request_status == 409:
                log.error("Not approved, the user has yet to approve your retrieve request.")
            elif request_status == 500:
                log.error("Internal server error, something failed to execute properly on the Prowl side.")
            else:
                log.error("Unknown error when sending Prowl message")


@event('plugin.register')
def register_plugin():
    plugin.register(OutputProwl, 'prowl', api_ver=2)
