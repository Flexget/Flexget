from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more

__name__ = 'xmpp'

log = logging.getLogger(__name__)


class XMPPNotifier(object):
    schema = {
        'type': 'object',
        'properties': {
            'sender': {'type': 'string', 'format': 'email'},
            'password': {'type': 'string'},
            'recipients': one_or_more({'type': 'string', 'format': 'email'}),
            'title': {'type': 'string'},
            'message': {'type': 'string'},
            'file_template': {'type': 'string', 'format': 'file_template'},
        },
        'required': ['sender', 'password', 'recipients'],
        'additionalProperties': False
    }

    __version__ = '0.2'

    def notify(self, data):
        try:
            import sleekxmpp  # noqa
        except ImportError as e:
            log.debug('Error importing SleekXMPP: %s', e)
            raise plugin.DependencyError('notify_xmpp', 'sleekxmpp', 'SleekXMPP module required. ImportError: %s', e)
        try:
            import dns  # noqa
        except ImportError:
            try:
                import dnspython  # noqa
            except ImportError as e:
                log.debug('Error importing dnspython: %s', e)
                raise plugin.DependencyError(__name__, 'dnspython', 'dnspython module required. ImportError: %s' % e)

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

        title = data['title']
        text = data['message']
        text = '%s\n%s' % (title, text)
        log.debug('Sending XMPP notification about: %s', text)
        logging.getLogger('sleekxmpp').setLevel(logging.CRITICAL)

        recipients = data['recipients']
        if not isinstance(recipients, list):
            recipients = [recipients]

        xmpp = SendMsgBot(data['sender'], data['password'], recipients, text)
        if xmpp.connect():
            xmpp.process(block=True)

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
    plugin.register(XMPPNotifier, __name__, api_ver=2, groups=['notifiers'])
