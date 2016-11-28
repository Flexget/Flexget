from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import hashlib

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from requests.exceptions import RequestException

__name__ = 'sms_ru'
log = logging.getLogger(__name__)

SMS_SEND_URL = 'http://sms.ru/sms/send'
SMS_TOKEN_URL = 'http://sms.ru/auth/get_token'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('sms.ru', '5 seconds'))


class SMSRuNotifier(object):
    """
    Sends SMS notification through sms.ru http api sms/send.
    Phone number is a login assigned to sms.ru account.

    Example:

      sms_ru:
        phone_number: <PHONE_NUMBER> (accepted format example: '79997776655')
        password: <PASSWORD>
        [message: <MESSAGE_TEXT>]

    """
    schema = {
        'type': 'object',
        'properties': {
            'phone_number': {'type': 'string'},
            'password': {'type': 'string'},
            'message': {'type': 'string'},
            'file_template': {'type': 'string'},
        },
        'additionalProperties': False,
        'required': ['phone_number', 'password']
    }

    def notify(self, phone_number, password, message, **kwargs):
        """
        Send an SMS RU notification

        :param str phone_number: Phone number to send to
        :param str password: Password
        :param str message: Message to send
        """
        try:
            token_response = requests.get(SMS_TOKEN_URL)
        except RequestException as e:
            raise PluginWarning('Could not get auth token: %s' % repr(e))

        sha512 = hashlib.sha512(password + token_response.text).hexdigest()

        # Build request params
        notification = {'login': phone_number,
                       'sha512': sha512,
                       'token': token_response.text,
                       'to': phone_number,
                       'text': message}

        try:
            response = requests.get(SMS_SEND_URL, params=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])
        else:
            if not response.text.find('100') == 0:
                raise PluginWarning(response.text)

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        # Send default values for backwards compatibility
        notify_config = {
            'to': [{__name__: config}],
            'scope': 'entries',
            'what': 'accepted'
        }
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)


@event('plugin.register')
def register_plugin():
    plugin.register(SMSRuNotifier, __name__, api_ver=2, groups=['notifiers'])
