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

__name__ = 'email'
log = logging.getLogger(__name__)


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
            'message': {'type': 'string'},
            'file_template': {'type': 'string'},
            'title': {'type': 'string'},
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

    def notify(self, to, message, title, smtp_host, smtp_port, smtp_username=None, smtp_password=None, smtp_tls=None,
               smtp_ssl=None, html=None, **kwargs):
        """
        Send an email notification

        :param str to: email `to` address
        :param str message: message body
        :param str title: message subject
        :param str smtp_host: smtp_host to use
        :param int smtp_port: port to use
        :param str smtp_username: smtp username if authentication is required
        :param str smtp_password: smtp password if authentication is required
        :param bool smtp_tls: enable tls
        :param bool smtp_ssl: enable ssl
        :param bool html: set content type to `html`
        :param kwargs: contains the `from` attribute since that is a reserved keyword
        """

        if not isinstance(to, list):
            to = [to]

        email = MIMEMultipart('alternative')
        email['To'] = ','.join(to)
        email['From'] = kwargs['from']
        email['Subject'] = title
        email['Date'] = formatdate(localtime=True)
        content_type = 'html' if html else 'plain'
        email.attach(MIMEText(message.encode('utf-8'), content_type, _charset='utf-8'))

        try:
            log.debug('sending email notification to %s:%s', smtp_host, smtp_port)
            mailServer = smtplib.SMTP_SSL if smtp_ssl else smtplib.SMTP
            mailServer = mailServer(smtp_host, smtp_port)
            if smtp_tls:
                mailServer.ehlo()
                mailServer.starttls()
                mailServer.ehlo()
        except (socket.error, OSError) as e:
            raise PluginWarning(str(e))

        try:
            if smtp_username:
                log.debug('logging in to smtp server using username: %s', smtp_username)
                mailServer.login(text_to_native_str(smtp_username), text_to_native_str(smtp_password))
            mailServer.sendmail(email['From'], to, email.as_string())
        except IOError as e:
            raise PluginWarning(str(e))

        mailServer.quit()

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
    plugin.register(EmailNotifier, __name__, api_ver=2, groups=['notifiers'])
