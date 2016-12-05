from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.plugin import DependencyError, PluginWarning

__name__ = 'xmpp'

log = logging.getLogger(__name__)


class XMPPNotifier(object):
    schema = {
        'type': 'object',
        'properties': {
            'sender': {'type': 'string'},
            'password': {'type': 'string'},
            'recipients': one_or_more({'type': 'string'}),
            'title': {'type': 'string'},
            'message': {'type': 'string'},
            'file_template': {'type': 'string'},
        },
        'required': ['sender', 'password', 'recipients'],
        'additionalProperties': False
    }

    __version__ = '1.0'

    def notify(self, title, message, sender, password, recipients, url=None, **kwargs):
        try:
            import sleekxmpp  # noqa
        except ImportError as e:
            log.debug('Error importing SleekXMPP: %s', e)
            raise DependencyError(__name__, 'sleekxmpp', 'SleekXMPP module required. ImportError: %s', e)
        try:
            import dns  # noqa
        except ImportError:
            try:
                import dnspython  # noqa
            except ImportError as e:
                log.debug('Error importing dnspython: %s', e)
                raise DependencyError(__name__, 'dnspython', 'dnspython module required. ImportError: %s' % e)

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

        message = '%s\n%s' % (title, message)
        log.debug('Sending XMPP notification about: %s', message)
        logging.getLogger('sleekxmpp').setLevel(logging.CRITICAL)

        if not isinstance(recipients, list):
            recipients = [recipients]

        xmpp = SendMsgBot(sender, password, recipients, message)
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
