import hashlib

from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession
from flexget.utils.requests import TimedLimiter

plugin_name = 'sms_ru'
logger = logger.bind(name=plugin_name)

SMS_SEND_URL = 'http://sms.ru/sms/send'
SMS_TOKEN_URL = 'http://sms.ru/auth/get_token'

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('sms.ru', '5 seconds'))


class SMSRuNotifier:
    """
    Sends SMS notification through sms.ru http api sms/send.
    Phone number is a login assigned to sms.ru account.

    Example:

      notify:
        entries:
          via:
            - sms_ru:
                phone_number: <PHONE_NUMBER> (accepted format example: '79997776655')
                password: <PASSWORD>

    """

    schema = {
        'type': 'object',
        'properties': {'phone_number': {'type': 'string'}, 'password': {'type': 'string'}},
        'additionalProperties': False,
        'required': ['phone_number', 'password'],
    }

    def notify(self, title, message, config):
        """
        Send an SMS RU notification
        """
        try:
            token_response = requests.get(SMS_TOKEN_URL)
        except RequestException as e:
            raise PluginWarning('Could not get auth token: %s' % repr(e))

        sha512 = hashlib.sha512(config['password'] + token_response.text).hexdigest()

        # Build request params
        notification = {
            'login': config['phone_number'],
            'sha512': sha512,
            'token': token_response.text,
            'to': config['phone_number'],
            'text': message,
        }

        try:
            response = requests.get(SMS_SEND_URL, params=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])
        else:
            if not response.text.find('100') == 0:
                raise PluginWarning(response.text)


@event('plugin.register')
def register_plugin():
    plugin.register(SMSRuNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
