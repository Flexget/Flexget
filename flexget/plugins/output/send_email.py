from __future__ import unicode_literals, division, absolute_import
import logging
import smtplib
import socket
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTPException
from email.utils import formatdate

from flexget import config_schema, manager, plugin
from flexget.event import event
from flexget.utils.template import render_from_task, get_template, RenderError
from flexget.utils.tools import merge_dict_from_to, MergeException
from flexget import validator

log = logging.getLogger('email')

# A dict which stores the email content from each task when plugin is configured globally
task_content = {}


def options_validator():
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


def prepare_config(config):
    config.setdefault('active', True)
    config.setdefault('smtp_host', 'localhost')
    config.setdefault('smtp_port', 25)
    config.setdefault('smtp_login', False)
    config.setdefault('smtp_username', '')
    config.setdefault('smtp_password', '')
    config.setdefault('smtp_tls', False)
    config.setdefault('smtp_ssl', False)
    config.setdefault('template', 'default.template')
    if not isinstance(config['to'], list):
        config['to'] = [config['to']]
    return config


@event('manager.execute.started')
def setup(manager):
    if not 'email' in manager.config:
        return
    config = prepare_config(manager.config['email'])
    config['global'] = True
    global task_content
    task_content = {}
    for task_name, task_config in manager.config['tasks'].iteritems():
        task_config.setdefault('email', {})
        try:
            merge_dict_from_to(config, task_config['email'])
        except MergeException as exc:
            raise plugin.PluginError('Failed to merge email config to task %s due to %s' % (task_name, exc))
        task_config.setdefault('email', config)


@event('manager.execute.completed')
def global_send(manager):
    if not 'email' in manager.config:
        return
    config = prepare_config(manager.config['email'])
    content = ''
    for task, text in task_content.iteritems():
        content += '_' * 30 + ' Task: %s ' % task + '_' * 30 + '\n'

        content += text + '\n'
    if not content:
        log.verbose('No tasks generated any email notifications. Not sending.')
        return
    if config.get('subject'):
        # If subject is specified, use it from the config
        subject = config['subject']
    elif config['template'].startswith('failed'):
        subject = '[FlexGet] Failures on task(s): %s' % ', '.join(task_content)
    else:
        subject = '[FlexGet] Notifications for task(s): %s' % ', '.join(task_content)
    send_email(subject, content, config)


def send_email(subject, content, config):
    """Send email at exit."""

    # prepare email message
    message = MIMEMultipart('alternative')
    message['To'] = ','.join(config['to'])
    message['From'] = config['from']
    message['Subject'] = subject
    message['Date'] = formatdate(localtime=True)
    content_type = 'html' if '<html>' in content else 'plain'
    message.attach(MIMEText(content.encode('utf-8'), content_type, _charset='utf-8'))

    # send email message
    if manager.manager.options.test:
        log.info('Would send email : %s' % message.as_string())
        log.info(content)
    else:
        log.verbose('Sending email.')
        try:
            if config['smtp_ssl']:
                if sys.version_info < (2, 6, 3):
                    raise plugin.PluginError('SSL email support requires python >= 2.6.3 due to python bug #4066, '
                                             'upgrade python or use TLS', log)
                    # Create a SSL connection to smtp server
                mailServer = smtplib.SMTP_SSL(config['smtp_host'], config['smtp_port'])
            else:
                mailServer = smtplib.SMTP(config['smtp_host'], config['smtp_port'])
                if config['smtp_tls']:
                    mailServer.ehlo()
                    mailServer.starttls()
                    mailServer.ehlo()
        except socket.error as e:
            log.warning('Socket error: %s' % e)
            return
        except SMTPException as e:
            # Ticket #1133
            log.warning('Unable to send email: %s' % e)
            return

        try:

            if config.get('smtp_username') and config.get('smtp_password'):
                mailServer.login(config['smtp_username'], config['smtp_password'])
            mailServer.sendmail(message['From'], config['to'], message.as_string())
        except IOError as e:
            # Ticket #686
            log.warning('Unable to send email! IOError: %s' % e)
            return
        except SMTPException as e:
            log.warning('Unable to send email! SMTPException: %s' % e)
            return

        mailServer.quit()


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

    Config multi-task example::

      global:
        email:
          from: xxx@xxx.xxx
          to: xxx@xxx.xxx
          smtp_host: smtp.host.com

      tasks:
        task1:
          rss: http://xxx
        task2:
          rss: http://yyy
          email:
            active: False
        task3:
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
        v = options_validator()
        v.accept('boolean', key='global')
        return v

    def on_task_output(self, task, config):
        """Count the email as an output"""

    def on_task_exit(self, task, config):
        """Send email at exit."""

        config = prepare_config(config)

        if not config['active']:
            return

        # don't send mail when learning
        if task.options.learn:
            return

        # generate email content
        if config.get('subject'):
            subject = config['subject']
        else:
            subject = '[FlexGet] {{task.name}}: '
            if task.aborted:
                subject += 'Aborted'
            elif task.failed:
                subject += '{{task.failed|length}} failed entries'
            else:
                subject += '{{task.accepted|length}} new entries downloaded'
        try:
            subject = render_from_task(subject, task)
        except RenderError as e:
            log.error('Error rendering email subject: %s' % e)
            return
        try:
            content = render_from_task(get_template(config['template'], 'email'), task)
        except RenderError as e:
            log.error('Error rendering email body: %s' % e)
            return

        if not content.strip():
            log.verbose('No content generated from template, not sending email.')
            return

        if config.get('global'):
            # Email plugin was configured at root, save the email output
            log.debug('Saving email content for task %s' % task.name)
            task_content[task.name] = content
        else:
            send_email(subject, content, config)

    # Also send the email on abort
    def on_task_abort(self, task, config):
        # The config may not be correct if the task is aborting
        try:
            self.on_task_exit(task, config)
        except Exception as e:
            log.info('Could not send abort email because email config is invalid.')
            # Log the exception to debug, in case something different is going wrong.
            log.debug('Email error:', exc_info=True)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputEmail, 'email', api_ver=2)


@event('config.register')
def register_config_key():
    config_schema.register_config_key('email', options_validator().schema())
