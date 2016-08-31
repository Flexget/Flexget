from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import smtplib
import socket
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

from flexget import config_schema, manager, plugin
from flexget.event import event
from flexget.utils.template import render_from_task, get_template, RenderError
from flexget.utils.tools import merge_dict_from_to, MergeException
from flexget.config_schema import one_or_more

log = logging.getLogger('email')

# A dict which stores the email content from each task when plugin is configured globally
task_content = {}


def prepare_config(config):
    if not isinstance(config['to'], list):
        config['to'] = [config['to']]
    return config


@event('manager.execute.started')
def setup(manager, options):
    if 'email' not in manager.config:
        return
    config = prepare_config(manager.config['email'])
    config['global'] = True
    global task_content
    task_content = {}
    for task_name, task_config in manager.config['tasks'].items():
        task_config.setdefault('email', {})
        try:
            merge_dict_from_to(config, task_config['email'])
        except MergeException as exc:
            raise plugin.PluginError('Failed to merge email config to task %s due to %s' % (task_name, exc))
        task_config.setdefault('email', config)


@event('manager.execute.completed')
def global_send(manager, options):
    if 'email' not in manager.config:
        return
    config = prepare_config(manager.config['email'])
    content = ''
    for task, text in task_content.items():
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
        except (socket.error, OSError) as e:
            # Ticket #1133
            log.warning('Unable to send email: %s' % e)
            return

        try:

            if config.get('smtp_username') and config.get('smtp_password'):
                # Forcing to use `str` type
                mailServer.login(str(config['smtp_username']), str(config['smtp_password']))
            mailServer.sendmail(message['From'], config['to'], message.as_string())
        except IOError as e:
            # Ticket #686
            log.warning('Unable to send email! IOError: %s' % e)
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

    schema = {
        'type': 'object',
        'properties': {
            'active': {'type': 'boolean', 'default': True},
            'to': one_or_more({'type': 'string'}),
            'from': {'type': 'string'},
            'smtp_host': {'type': 'string', 'default': 'localhost'},
            'smtp_port': {'type': 'integer', 'default': 25},
            'smtp_login': {'type': 'boolean', 'default': False},
            'smtp_username': {'type': 'string', 'default': ''},
            'smtp_password': {'type': 'string', 'default': ''},
            'smtp_tls': {'type': 'boolean', 'default': False},
            'smtp_ssl': {'type': 'boolean', 'default': False},
            'template': {'type': 'string', 'default': 'default.template'},
            'subject': {'type': 'string'},
            'global': {'type': 'boolean'}
        },
        'required': ['to', 'from'],
        'additionalProperties': False,
    }

    @plugin.priority(0)
    def on_task_output(self, task, config):
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

    def on_task_abort(self, task, config):
        if not task.silent_abort:
            self.on_task_output(task, config)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputEmail, 'email', api_ver=2)


@event('config.register')
def register_config_key():
    config_schema.register_config_key('email', OutputEmail.schema)
