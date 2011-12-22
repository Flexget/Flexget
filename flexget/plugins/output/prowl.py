__version__ = 0.1

from httplib import HTTPSConnection
from urllib import urlencode
import logging
from flexget.plugin import get_plugin_by_name, register_plugin
from flexget.utils.template import RenderError

log = logging.getLogger('prowl')

headers = {'User-Agent': "FlexGet Prowl plugin/%s" % str(__version__),
           'Content-type': "application/x-www-form-urlencoded"}


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

    def on_process_start(self, feed, config):
        """
            Register the usable set: keywords.
        """
        set_plugin = get_plugin_by_name('set')
        set_plugin.instance.register_keys({'apikey': 'text', 'application': 'text',
                                           'event': 'text', 'priority': 'integer'})

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('apikey', '')
        config.setdefault('application', 'FlexGet')
        config.setdefault('event', 'New release')
        config.setdefault('priority', 0)
        return config

    def on_feed_output(self, feed, config):
        config = self.prepare_config(config)
        for entry in feed.accepted:

            if feed.manager.options.test:
                log.info("Would send prowl message about: %s", entry['title'])
                continue

            # get the parameters
            apikey = entry.get('apikey', config['apikey'])
            application = entry.get('application', config['application'])
            event = entry.get('event', config['event'])
            priority = entry.get('priority', config['priority'])
            description = config.get('description', entry['title'])

            # If description has jinja template, render it
            try:
                description = entry.render(description)
            except RenderError, e:
                description = entry['title']
                log.error('Error rendering jinja description: %s' % e)

            # Open connection
            h = HTTPSConnection('prowl.weks.net')

            # Send the request
            data = {'priority': priority, 'application': application, 'apikey': apikey,
                    'event': event, 'description': description}
            h.request("POST", "/publicapi/add", headers=headers, body=urlencode(data))

            # Check if it succeeded
            response = h.getresponse()
            request_status = response.status

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
