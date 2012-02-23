import logging
import smtplib
import socket
from email.message import Message
from smtplib import SMTPException
from flexget.plugin import PluginError, PluginWarning, register_plugin
from flexget.utils.template import render_from_feed, get_template, RenderError

log = logging.getLogger('email')


class OutputEmail(object):

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
                     Due to a bug in python, this only works in python 2.6.3 and up
    active           Is this plugin active or not
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

    Config multi-feed example::

      global:
        email:
          from: xxx@xxx.xxx
          to: xxx@xxx.xxx
          smtp_host: smtp.host.com

      feeds:
        feed1:
          rss: http://xxx
        feed2:
          rss: http://yyy
          email:
            active: False
        feed3:
          rss: http://zzz
          email:
            to: zzz@zzz.zzz

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
        active: True
        smtp_host: localhost
        smtp_port: 25
        smtp_login: False
        smtp_username:
        smtp_password:
        smtp_tls: False
        smtp_ssl: False
    """

    def validator(self):
        from flexget import validator
        email = validator.factory('dict')
        email.accept('boolean', key='active')
        email.accept('text', key='to', required=True)
        email.accept('list', key='to', required=True).accept('text')
        email.accept('text', key='from', required=True)
        email.accept('text', key='smtp_host')
        email.accept('integer', key='smtp_port')
        email.accept('boolean', key='smtp_login')
        email.accept('text', key='smtp_username')
        email.accept('text', key='smtp_password')
        email.accept('boolean', key='smtp_tls')
        email.accept('boolean', key='smtp_ssl')
        email.accept('text', key='template')
        email.accept('text', key='subject')
        return email

    def prepare_config(self, config):
        config.setdefault('active', True)
        config.setdefault('smtp_host', 'localhost')
        config.setdefault('smtp_port', 25)
        config.setdefault('smtp_login', False)
        config.setdefault('smtp_username', '')
        config.setdefault('smtp_password', '')
        config.setdefault('smtp_tls', False)
        config.setdefault('smtp_ssl', False)
        config.setdefault('template', 'default.template')
        config.setdefault('subject', '[FlexGet] {{feed.name}}: {{feed.accepted|length}} new entries downloaded')
        if not isinstance(config['to'], list):
            config['to'] = [config['to']]
        return config

    def on_feed_output(self, feed, config):
        """Count the email as an output"""

    def on_feed_exit(self, feed, config):
        """Send email at exit."""
        config = self.prepare_config(config)

        if not config['active']:
            return

        # don't send mail when learning
        if feed.manager.options.learn:
            return

        # generate email content
        try:
            subject = render_from_feed(config['subject'], feed)
        except RenderError, e:
            log.error('Error rendering email subject: %s' % e)
            return
        try:
            content = render_from_feed(get_template(config['template'], 'email'), feed)
        except RenderError, e:
            log.error('Error rendering email body: %s' % e)
            return
        if not content.strip():
            log.verbose('No content generated from template, not sending email.')
            return

        # prepare email message
        message = Message()
        message['To'] = ','.join(config['to'])
        message['From'] = config['from']
        message['Subject'] = subject
        message.set_payload(content.encode('utf-8'))
        message.set_charset('utf-8')

        # send email message
        if feed.manager.options.test:
            log.info('Would send email : %s' % message.as_string())
            log.info(content)
        else:
            try:
                if config['smtp_ssl']:
                    import sys
                    if sys.version_info < (2, 6, 3):
                        raise PluginError('SSL email support requires python >= 2.6.3 due to python bug #4066, upgrade python or use TLS', log)
                    # Create a SSL connection to smtp server
                    mailServer = smtplib.SMTP_SSL(config['smtp_host'], config['smtp_port'])
                else:
                    mailServer = smtplib.SMTP(config['smtp_host'], config['smtp_port'])
                    if config['smtp_tls']:
                        mailServer.ehlo()
                        mailServer.starttls()
            except socket.error, e:
                raise PluginWarning('Socket error: %s' % e, log)
            except SMTPException, e:
                # Ticket #1133
                raise PluginWarning('Unable to send email: %s' % e, log)

            try:

                if config.get('smtp_username') and config.get('smtp_password'):
                    mailServer.login(config['smtp_username'], config['smtp_password'])
                mailServer.sendmail(message['From'], config['to'], message.as_string())
            except IOError, e:
                # Ticket #686
                raise PluginWarning('Unable to send email! IOError: %s' % e, log)
            except SMTPException, e:
                raise PluginWarning('Unable to send email! SMTPException: %s' % e, log)

            mailServer.quit()

register_plugin(OutputEmail, 'email', api_ver=2)
