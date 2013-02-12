from __future__ import unicode_literals, division, absolute_import
import logging
import hashlib

from flexget.plugin import register_plugin, priority
from flexget.utils.template import RenderError

__version__ = 0.1

log = logging.getLogger("sms_ru")

client_headers = {"User-Agent": "FlexGet sms_ru plugin/%s" % str(__version__)}
sms_send_url = "http://sms.ru/sms/send"
sms_token_url = "http://sms.ru/auth/get_token"


class OutputSMSru(object):
    """
    Sends SMS notification through sms.ru http api sms/send.
    Phone number is a login assigned to sms.ru account.

    Example:

      sms_ru:
        phonenumber: <PHONE_NUMBER> (accepted format example: "79997776655")
        password: <PASSWORD>
        [message: <MESSAGE_TEXT>] (default: "accepted {{title}}" -- accepts Jinja)

    Configuration parameters are also supported from entries (eg. through set).

    """

    def validator(self):
        from flexget import validator
        config = validator.factory("dict")
        config.accept("text", key="phonenumber", required=True)
        config.accept("text", key="password", required=True)
        config.accept("text", key="message", required=False)
        return config

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {"enabled": config}

        # Set the defaults
        config.setdefault("message", "accepted {{title}}")
        return config

    # Run last to make sure other outputs are successful before sending notification
    @priority(0)
    def on_task_output(self, task, config):
        # Get the parameters
        config = self.prepare_config(config)

        phonenumber = config["phonenumber"]
        password = config["password"]

        # Backend provides temporary token
        token_response = task.requests.get(sms_token_url, headers=client_headers, raise_status=False)

        if token_response.status_code == 200:
            log.debug("Got auth token")
            # Auth method without api_id based on hash of password combined with token
            sha512 = hashlib.sha512(password + token_response.text).hexdigest()
        else:
            log.error("Error getting auth token")

        # Loop through the accepted entries
        for entry in task.accepted:
            # Set message from entry
            message = config["message"]

            # Attempt to render the message field
            try:
                message = entry.render(message)
            except RenderError, e:
                log.debug("Problem rendering 'message': %s" % e)
                message = "accepted %s" % entry["title"]

            # Check for test mode
            if task.manager.options.test:
                log.info("Test mode. Processing for %s" % phonenumber)
                log.info("Message: %s" % message)

            # Build request params
            send_params = {'login': phonenumber,
                           'sha512': sha512,
                           'token': token_response.text,
                           'to': phonenumber,
                           'text': message}
            if task.manager.options.test:
                send_params.update({'test': 1})

            # Make the request
            response = task.requests.get(sms_send_url, params=send_params, headers=client_headers, raise_status=False)

            # Get resul code from sms.ru backend returned in body
            result_text = response.text

            # Check if it succeeded
            if response.text.find("100") == 0:
                log.debug("SMS notification for %s sent" % phonenumber)
            else:
                log.error("SMS was not sent. Server response was %s" % response.text)

register_plugin(OutputSMSru, "sms_ru", api_ver=2)
