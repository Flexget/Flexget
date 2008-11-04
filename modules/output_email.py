import logging
import smtplib
import email.Message
from validator import DictValidator

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('email')

class OutputEmail:

    """
        Send an e-mail with the list of all succeeded (downloaded) entries.

        Config:
          from          : the email address from which the email will be sent (required)
          to            : the email address of the recipient (required)
          smtp_host     : the host of the smtp server
          smtp_port     : the port of the smtp server
          smtp_login    : should we use anonymous mode or login to the smtp server ? 
          smtp_username : the username to use to connect to the smtp server
          smtp_password : the password to use to connect to the smtp server
          active        : is this module active or not ?

        Config basic example:
        
        email:
          from: xxx@xxx.xxx
          to: xxx@xxx.xxx
          smtp_host: smtp.host.com

        Config example with smtp login:
        
        email:
          from: xxx@xxx.xxx
          to: xxx@xxx.xxx
          smtp_host: smtp.host.com
          smtp_port: 25
          smtp_login: true
          smtp_username: my_smtp_login
          smtp_password: my_smtp_password

        Config multi-feed example:
        
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

        Default values for the config elements:

        email:
          active: True
          smtp_host: localhost
          smtp_port: 25
          smtp_login: False
          smtp_username: 
          smtp_password: 
    """

    def register(self, manager, parser):
        manager.register('email')

    def validate(self, config):
        """Validate given configuration"""
        email = DictValidator()
        email.accept('active', bool)
        email.accept('to', str, require=True)
        email.accept('from', str, require=True)
        email.accept('smtp_host', str)
        email.accept('smtp_port', int)
        email.accept('smtp_login', bool)
        email.accept('smtp_username', str)
        email.accept('smtp_password', str)
        email.validate(config)
        return email.errors.messages
        
    def get_config(self, feed):
        config = feed.config['email']
        config.setdefault('active', True)
        config.setdefault('smtp_host', 'localhost')
        config.setdefault('smtp_port', 25)
        config.setdefault('smtp_login', False)
        config.setdefault('smtp_username', '')
        config.setdefault('smtp_password', '')
        return config

    def feed_exit(self, feed):
        """Send email at exit."""
        config = self.get_config(feed)

        if not config['active']:
            return
            
        # don't send mail when learning
        if feed.manager.options.learn:
            return

        entries_count = len(feed.entries)
        if entries_count == 0:
            return # don't send empty emails

        # generate email content
        subject = "[FlexGet] %s : %d new entries downloaded" % (feed.name, entries_count)
        content = """Hi,

FlexGet has just downloaded %d new entries for feed %s : 
        """ % (entries_count, feed.name)
        for entry in feed.entries:
            content += "\n - %s (%s)" % (entry['title'], entry['url'])
            entry_path = entry.get('path', feed.config.get('download'))
            entry_filename = entry.get('filename', entry['title'])
            if entry_path:
                content += " => %s (%s)" % (entry_path, entry_filename)
                
        content += "\n\n"

        # prepare email message
        message = email.Message.Message()
        message["To"] = config['to']
        message["From"] = config['from']
        message["Subject"] = subject
        message.set_payload(content)

        # send email message
        if feed.manager.options.test:
            log.info('Would send email : %s' % message.as_string())
        else:
            mailServer = smtplib.SMTP(config['smtp_host'], config['smtp_port'])
            if config['smtp_login']:
                mailServer.login(config['smtp_username'], config['smtp_password'])
            mailServer.sendmail(message["From"], message["To"], message.as_string())
            mailServer.quit()
