from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError, render_from_task
from flexget.config_schema import one_or_more

log = logging.getLogger('notify_xmpp')


try:
    import sleekxmpp
    
    class SendMsgBot(sleekxmpp.ClientXMPP):
    
        def __init__(self, jid, password, recipients, message):
            sleekxmpp.ClientXMPP.__init__(self, jid, password)
            self.recipients = recipients
            self.msg = message
            self.add_event_handler("session_start", self.start, threaded=True)
            self.register_plugin('xep_0030')  # Service Discovery
            self.register_plugin('xep_0199')  # XMPP Ping
    
        def start(self, xmpp_event):
            for recipient in self.recipients:
                self.send_presence(pto=recipient)
                self.send_message(mto=recipient, mbody=self.msg, mtype='chat')
            self.disconnect(wait=True)

except ImportError:
    # If sleekxmpp is not found, errors will be shown later
    pass
        

class OutputNotifyXmpp(object):
    
    schema = {
        'type': 'object',
        'properties': {
            'sender': {'type': 'string', 'format': 'email'},
            'password': {'type': 'string'},
            'recipients': one_or_more({'type': 'string', 'format': 'email'}),
            'title': {'type': 'string', 'default': '{{task.name}}'},
            'text': {'type': 'string', 'default': '{{title}}'}
        },
        'required': ['sender', 'password', 'recipients'],
        'additionalProperties': False
    }
    
    __version__ = '0.1'

    def on_task_start(self, task, config):
        try:
            import sleekxmpp
        except ImportError as e:
            log.debug('Error importing SleekXMPP: %s' % e)
            raise plugin.DependencyError('notify_xmpp', 'sleekxmpp', 'SleekXMPP module required. ImportError: %s' % e)
        try:
            import dns
        except ImportError:
            try:
                import dnspython
            except ImportError as e:
                log.debug('Error importing dnspython: %s' % e)
                raise plugin.DependencyError('notify_xmpp',
                                             'dnspython',
                                             'dnspython module required. ImportError: %s' % e)
    
    def on_task_output(self, task, config):
        """
        Configuration::
            notify_xmpp:
                title: Message title, supports jinja templating, default {{task.name}}
                text: Message text, suports jinja templating, default {{title}}
        """
        if not config or not task.accepted:
            return
        
        title = config['title']
        try:
            title = render_from_task(title, task)
            log.debug('Setting message title to :%s', title)
        except RenderError as e:
            log.error('Error setting title message: %s' % e)
        items = []
        for entry in task.accepted:
            try:
                items.append(entry.render(config['text']))
            except RenderError as e:
                log.error('Error setting text message: %s' % e)
        text = '%s\n%s' % (title, '\n'.join(items))
        
        log.verbose('Send XMPP notification about: %s', ' - '.join(items))
        logging.getLogger('sleekxmpp').setLevel(logging.CRITICAL)

        recipients = config.get('recipients', [])
        if not isinstance(recipients, list):
            recipients = [recipients]

        xmpp = SendMsgBot(config['sender'], config['password'], recipients, text)
        if xmpp.connect():
            xmpp.process(block=True)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputNotifyXmpp, 'notify_xmpp', api_ver=2)
