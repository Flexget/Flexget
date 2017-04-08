from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import xml.etree.ElementTree as ET

from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from flexget.utils.tools import merge_by_prefix

plugin_name = 'prowl'
log = logging.getLogger(plugin_name)

PROWL_URL = 'https://api.prowlapp.com/publicapi/add'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('prowlapp.com', '5 seconds'))


class ProwlNotifier(object):
    """
    Send prowl notifications

    Example::

      prowl:
        api_key: xxxxxxx
        [application: application name, default FlexGet]
        [event: event title, default New Release]
        [priority: -2 - 2 (2 = highest), default 0]
        [description: notification to send]

    """
    schema = {
        'type': 'object',
        'properties': {
            'api_key': one_or_more({'type': 'string'}),
            'application': {'type': 'string', 'default': 'FlexGet'},
            'priority': {'type': 'integer', 'minimum': -2, 'maximum': 2},
            'url': {'type': 'string'},
            'provider_key': {'type': 'string'}
        },
        'required': ['api_key'],
        'additionalProperties': False
    }

    def notify(self, title, message, config, entry=None):
        """
        Send a Prowl notification
        """
        # Enables using 'set' plugin to override plugin config, using plugin name and underscore as prefix
        # Example:
        #
        # set:
        #   pushover_url: http://newurl.com
        #

        if entry:
            merge_by_prefix(plugin_name + '_', dict(entry), config)
        notification = {'application': config.get('application'), 'event': title, 'description': message,
                        'url': config.get('url'), 'priority': config.get('priority'),
                        'providerkey': config.get('provider_key')}

        if isinstance(config['api_key'], list):
            config['api_key'] = [config['api_key']]
        notification['apikey'] = config['api_key']

        try:
            response = requests.post(PROWL_URL, data=notification)
        except RequestException as e:
            raise PluginWarning(repr(e))

        request_status = ET.fromstring(response.content)
        error = request_status.find('error')
        if error is not None:
            raise PluginWarning(error.text)
        else:
            success = request_status.find('success').attrib
            log.debug('prowl notification sent. Notifications remaining until next reset: %s. '
                      'Next reset will occur in %s minutes', success['remaining'], success['resetdate'])


@event('plugin.register')
def register_plugin():
    plugin.register(ProwlNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
