from __future__ import unicode_literals, division, absolute_import
import logging

from requests import RequestException

from flexget.plugin import register_plugin, priority
from flexget.utils.template import RenderError

__version__ = 0.1

log = logging.getLogger('prowl')

headers = {'User-Agent': 'FlexGet Prowl plugin/%s' % str(__version__)}


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

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='apikey', required=True)
        config.accept('text', key='application')
        config.accept('text', key='event')
        config.accept('integer', key='priority')
        config.accept('text', key='description')
        return config

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('apikey', '')
        config.setdefault('application', 'FlexGet')
        config.setdefault('event', 'New release')
        config.setdefault('priority', 0)
        return config

    # Run last to make sure other outputs are successful before sending notification
    @priority(0)
    def on_task_output(self, task, config):
        config = self.prepare_config(config)
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

            url = 'https://prowl.weks.net/publicapi/add'
            data = {'priority': priority, 'application': application, 'apikey': apikey,
                    'event': event, 'description': description}

            if task.manager.options.test:
                log.info('Would send prowl message about: %s', entry['title'])
                log.debug('options: %s' % data)
                continue

            try:
                response = task.requests.post(url, headers=headers, data=data, raise_status=False)
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
            elif request_status == 500:
                log.error("Internal server error, something failed to execute properly on the Prowl side.")
            else:
                log.error("Unknown error when sending Prowl message")

register_plugin(OutputProwl, 'prowl', api_ver=2)
