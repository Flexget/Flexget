from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.requests import Session
from flexget.plugin import PluginWarning

from requests.exceptions import RequestException

plugin_name = 'ifttt'
log = logging.getLogger(plugin_name)


class IFTTTNotifier(object):
    """
    Push the notification to an IFTTT webhook.

    Configuration options

    ===============  ===================================================================
    Option           Description
    ===============  ===================================================================
    event            The event endpoint to trigger (required)
    keys             List of auth  keys to send the notification to. (required)
    ===============  ===================================================================

    Config basic example::

      notify:
        task:
          via:
            - ifttt:
                event: download_added
                keys:
                    - deadebeef123
    """

    def __init__(self):
        self.session = Session()
        self.url_template = 'https://maker.ifttt.com/trigger/{}/with/key/{}'

    schema = {
        'type': 'object',
        'properties': {'event': {'type': 'string'}, 'keys': one_or_more({'type': 'string'})},
        'required': ['event', 'keys'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send notification to ifttt webhook.

        The notification will be sent to https://maker.ifttt.com/trigger/{event}/with/key/{key}'
        with the values for the config, with a json body setting 'value1' to the message title,
        and 'value2' to the message body.

        If multiple keys are provided the event will be triggered for all of them.

        :param str message: message body
        :param str title: message subject
        :param dict config: plugin config
        """
        config = self.prepare_config(config)
        notification_body = {'value1': title, 'value2': message}
        errors = False
        for key in config['keys']:
            url = self.url_template.format(config['event'], key)
            try:
                self.session.post(url, json=notification_body)
                log.info("Sent notification to key: %s", key)
            except RequestException as e:
                log.error("Error sending notification to key %s: %s", key, e)
                errors = True
        if errors:
            raise PluginWarning("Failed to send notifications")

    def prepare_config(self, config):
        if not isinstance(config['keys'], list):
            config['keys'] = [config['keys']]
        return config


@event('plugin.register')
def register_plugin():
    plugin.register(IFTTTNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
