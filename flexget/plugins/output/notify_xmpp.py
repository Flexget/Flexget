from __future__ import unicode_literals, division, absolute_import
import logging
import sleekxmpp

from flexget.plugin import register_plugin
from flexget.utils.template import RenderError, render_from_task

log = logging.getLogger('notify_xmpp')


class SendMsgBot(sleekxmpp.ClientXMPP):

    def __init__(self, jid, password, recipient, message):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)
        # The message we wish to send, and the JID that
        # will receive it.
        self.recipient = recipient
        self.msg = message
        # The session_start event will be triggered when
        # the bot establishes its connection with the server
        # and the XML streams are ready for use. We want to
        # listen for this event so that we we can initialize
        # our roster.
        self.add_event_handler("session_start", self.start, threaded=True)

    def start(self, event):
        """
        Process the session_start event.

        Typical actions for the session_start event are
        requesting the roster and broadcasting an initial
        presence stanza.

        Arguments:
            event -- An empty dictionary. The session_start
                     event does not provide any additional
                     data.
        """
        self.send_presence()
        self.get_roster()
        self.send_message(mto=self.recipient,
                          mbody=self.msg,
                          mtype='chat')
        # Using wait=True ensures that the send queue will be
        # emptied before ending the session.
        self.disconnect(wait=True)
        
class OutputNotifyXmpp(object):
    
    schema = {
        'type': 'object',
        'properties': {
            'sender': {'type': 'string', 'format': 'email'},
            'password': {'type': 'string'},
            'recipient': {'type': 'string', 'format': 'email'},
            'title': {'type': 'string', 'default': '{{task.name}}'},
            'text': {'type': 'string', 'default': '{{title}}'}
        },
        'required': ['sender', 'password', 'recipient'],
        'additionalProperties': False
    }
    
    __version__ = '0.1'
    
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
        
        xmpp = SendMsgBot(config['sender'], config['password'], config['recipient'], text)
        xmpp.register_plugin('xep_0030') # Service Discovery
        xmpp.register_plugin('xep_0199') # XMPP Ping
        if xmpp.connect():
            xmpp.process(block=True)


register_plugin(OutputNotifyXmpp, 'notify_xmpp', api_ver=2)
