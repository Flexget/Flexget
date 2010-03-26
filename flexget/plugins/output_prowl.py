__version__ = 0.1

from httplib import HTTPSConnection
from urllib import urlencode
import logging
from flexget.plugin import *

log = logging.getLogger('prowl')

headers = {'User-Agent': "FlexGet Prowl plugin/%s" % str(__version__), 
           'Content-type': "application/x-www-form-urlencoded"}


class OutputProwl:
    """
    prowl:
      apikey: xxxxxxx
      [event: event title]
      [priority: -2 - 2 (2 = highest), default 0]
    """
    
    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='apikey', required=True)
        config.accept('text', key='event')
        config.accept('number', key='priority')
        return config

    def on_feed_output(self, feed):
        for entry in feed.accepted:
            if feed.manager.options.test:
                log.info("Would send prowl message about: %s", entry['title'])
                continue

            # get the parameters
            config = feed.config['prowl']
            apikey = config['apikey']
            event = config.get('event', 'New release')
            priority = config.get('priority', 0)
            description = entry['title']
            
            # Open connection
            h = HTTPSConnection('prowl.weks.net')
            
            # Send the request
            data = {'priority': priority, 'application': 'FlexGet', 'apikey': apikey, 'event': event, 'description': description}
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

register_plugin(OutputProwl, 'prowl')
