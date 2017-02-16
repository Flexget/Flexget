from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.utils import text_to_native_str

import logging
import smtplib
import socket

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.plugin import PluginWarning

plugin_name = 'email'
log = logging.getLogger(plugin_name)


class EmailNotifier(object):
    """
    Send an e-mail with the list of all succeeded (downloaded) entries.

    Configuration options

    ===============  ===================================================================
    Option           Description
    ===============  ===================================================================
    from             The email address from which the email will be sent (required)
    to               The email address of the recipient (required)
    smtp_host        The host of the smtp server
    smtp_port        The port of the smtp server
    smtp_username    The username to use to connect to the smtp server
    smtp_password    The password to use to connect to the smtp server
    smtp_tls         Should we use TLS to connect to the smtp server
    smtp_ssl         Should we use SSL to connect to the smtp server
    ===============  ===================================================================

    Config basic example::

      email:
        from: xxx@xxx.xxx
        to: xxx@xxx.xxx
        smtp_host: smtp.host.com

    Config example with smtp login::

      email:
        from: xxx@xxx.xxx
        to: xxx@xxx.xxx
        smtp_host: smtp.host.com
        smtp_port: 25
        smtp_login: true
        smtp_username: my_smtp_login
        smtp_password: my_smtp_password
        smtp_tls: true

    GMAIL example::

      from: from@gmail.com
      to: to@gmail.com
      smtp_host: smtp.gmail.com
      smtp_port: 587
      smtp_login: true
      smtp_username: gmailUser
      smtp_password: gmailPassword
      smtp_tls: true

    Default values for the config elements::

      email:
        smtp_host: localhost
        smtp_port: 25
        smtp_login: False
        smtp_username:
        smtp_password:
        smtp_tls: False
        smtp_ssl: False
    """

    schema = {
        'type': 'object',
        'properties': {
            'to': one_or_more({'type': 'string', 'format': 'email'}),
            'from': {'type': 'string', 'default': 'flexget_notifer@flexget.com', 'format': 'email'},
            'smtp_host': {'type': 'string', 'default': 'localhost'},
            'smtp_port': {'type': 'integer', 'default': 25},
            'smtp_username': {'type': 'string'},
            'smtp_password': {'type': 'string'},
            'smtp_tls': {'type': 'boolean', 'default': False},
            'smtp_ssl': {'type': 'boolean', 'default': False},
            'html': {'type': 'boolean', 'default': False},
        },
        'required': ['to'],
        'dependencies': {
            'smtp_username': ['smtp_password'],
            'smtp_password': ['smtp_username'],
            'smtp_ssl': ['smtp_tls']
        },
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send an email notification

        :param str message: message body
        :param str title: message subject
        :param dict config: email plugin config
        """

        if not isinstance(config['to'], list):
            config['to'] = [config['to']]

        email = MIMEMultipart('alternative')
        email['To'] = ','.join(config['to'])
        email['From'] = config['from']
        email['Subject'] = title
        email['Date'] = formatdate(localtime=True)
        content_type = 'html' if config['html'] else 'plain'
        email.attach(MIMEText(message.encode('utf-8'), content_type, _charset='utf-8'))

        try:
            log.debug('sending email notification to %s:%s', config['smtp_host'], config['smtp_port'])
            mail_server = smtplib.SMTP_SSL if config['smtp_ssl'] else smtplib.SMTP
            mail_server = mail_server(config['smtp_host'], config['smtp_port'])
            if config['smtp_tls']:
                mail_server.ehlo()
                mail_server.starttls()
                mail_server.ehlo()
        except (socket.error, OSError) as e:
            raise PluginWarning(str(e))

        try:
            if config.get('smtp_username'):
                # Forcing to use `str` type
                log.debug('logging in to smtp server using username: %s', config['smtp_username'])
                mail_server.login(text_to_native_str(config['smtp_username']),
                                  text_to_native_str(config['smtp_password']))
            mail_server.sendmail(email['From'], config['to'], email.as_string())
        except IOError as e:
            raise PluginWarning(str(e))

        mail_server.quit()


@event('plugin.register')
def register_plugin():
    plugin.register(EmailNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
