import getpass
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from smtplib import SMTPAuthenticationError, SMTPSenderRefused, SMTPServerDisconnected

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import PluginWarning

plugin_name = 'email'
logger = logger.bind(name=plugin_name)


class EmailNotifier:
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

      notify:
        entries:
          via:
            - email:
                from: xxx@xxx.xxx
                to: xxx@xxx.xxx
                smtp_host: smtp.host.com

    Config example with smtp login::

      notify:
        entries:
          via:
            - email:
                from: xxx@xxx.xxx
                to: xxx@xxx.xxx
                smtp_host: smtp.host.com
                smtp_port: 25
                smtp_login: true
                smtp_username: my_smtp_login
                smtp_password: my_smtp_password
                smtp_tls: true

    GMAIL example::

      notify:
        entries:
          via:
            - email:
                from: from@gmail.com
                to: to@gmail.com
                smtp_host: smtp.gmail.com
                smtp_port: 587
                smtp_login: true
                smtp_username: gmailUser
                smtp_password: gmailPassword
                smtp_tls: true

    Default values for the config elements::

      notify:
        entries:
          via:
            - email:
                smtp_host: localhost
                smtp_port: 25
                smtp_login: False
                smtp_username:
                smtp_password:
                smtp_tls: False
                smtp_ssl: False
    """

    def __init__(self):
        self.mail_server = None
        self.host = None
        self.port = None
        self.username = None
        self.password = None
        self.ssl = None
        self.tls = None

    def connect_to_smtp_server(self, config):
        self.host = config['smtp_host']
        self.port = config['smtp_port']
        self.ssl = config['smtp_ssl']
        self.tls = config['smtp_tls']
        self.username = config.get('smtp_username')
        self.password = config.get('smtp_password')
        try:
            logger.debug('connecting to smtp server {}:{}', self.host, self.port)
            self.mail_server = smtplib.SMTP_SSL if self.ssl else smtplib.SMTP
            self.mail_server = self.mail_server(self.host, self.port)
            if self.tls:
                self.mail_server.ehlo()
                self.mail_server.starttls()
                self.mail_server.ehlo()
        except (socket.error, OSError) as e:
            raise PluginWarning(str(e))

        try:
            if self.username:
                # Forcing to use `str` type
                logger.debug('logging in to smtp server using username: {}', self.username)
                self.mail_server.login(self.username, self.password)
        except (OSError, SMTPAuthenticationError) as e:
            raise PluginWarning(str(e))

    schema = {
        'type': 'object',
        'properties': {
            'to': one_or_more({'type': 'string', 'format': 'email'}),
            'from': {
                'type': 'string',
                'default': 'flexget_notifer@flexget.com',
                'format': 'email',
            },
            'autofrom': {'type': 'boolean', 'default': False},
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
            'smtp_ssl': ['smtp_tls'],
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
        email['From'] = (
            getpass.getuser() + '@' + socket.getfqdn() if config['autofrom'] else config['from']
        )
        email['Subject'] = title
        email['Date'] = formatdate(localtime=True)
        content_type = 'html' if config['html'] else 'plain'
        email.attach(MIMEText(message.encode('utf-8'), content_type, _charset='utf-8'))

        # Making sure mail server connection will remain open per host or username
        # (in case several mail servers are used in the same task)
        if not self.mail_server or not (
            self.host == config['smtp_host'] and self.username == config.get('smtp_username')
        ):
            self.connect_to_smtp_server(config)

        connection_error = None
        while True:
            try:
                self.mail_server.sendmail(email['From'], config['to'], email.as_string())
                break
            except (SMTPServerDisconnected, SMTPSenderRefused) as e:
                if not connection_error:
                    self.connect_to_smtp_server(config)
                    connection_error = e
                else:
                    raise PluginWarning('Could not connect to SMTP server: %s' % str(e))


@event('plugin.register')
def register_plugin():
    plugin.register(EmailNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
