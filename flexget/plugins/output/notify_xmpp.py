from __future__ import unicode_literals, division, absolute_import
import logging
import time

from flexget.plugin import register_plugin, priority, DependencyError, PluginError
from flexget.utils.template import RenderError, render_from_task

log = logging.getLogger('notify_xmpp')


class OutputNotifyXmpp(object):

    schema = {
        'type': 'object',
        'properties': {
            'bot_jid': {'type': 'string'},
            'bot_password': {'type': 'string'},
            'bot_server': {'type': 'string'},
            'recipient': {'type': 'string', 'format': 'email'},         # TODO: list instead of string/email
            'title': {'type': 'string', 'default': '{{task.name}}'},
            'text': {'type': 'string', 'default': '{{title}}'}
        },
        'required': ['bot_jid', 'bot_password', 'bot_server', 'recipient'],
        'additionalProperties': False
    }

    __version__ = '0.1'
    
    @priority(0)
    def on_task_start(self, task, config):
        try:
            import xmpp
        except ImportError as e:
            log.debug('Error importing XMPP: %s' % e)
            raise DependencyError('notify_xmpp', 'xmpp', 'XMPP module required. ImportError: %s' % e)

    def on_task_output(self, task, config):
        """
        Configuration::
            notify_xmpp:
                title: Message title, supports jinja templating, default {{task.name}}
                text: Message text, suports jinja templating, default {{title}}
        """
        import xmpp

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
        log.verbose("Send Notify-XMPP notification about: %s", " - ".join(items))

        jid = xmpp.protocol.JID(config['bot_jid'])
        client = xmpp.Client(jid.getDomain(), debug=[])

        connection = client.connect()
        if not connection:
            raise PluginError('Could not connect to XMPP server %s (Full JID supplied?)' % jid.getDomain())
        else:
            log.debug('Connected to XMPP server %s' % connection)

        auth = client.auth(jid.getNode(), config['bot_password'], resource=jid.getResource())
        if not auth:
            raise PluginError('Could not authenticate as %s' % config['bot_jid'])
        else:
            log.debug('Authenticated using %s' % auth)

        client.sendInitPresence()
        message = xmpp.Message(config['recipient'], '%s\n%s' % (title, '\n'.join(items)))
        message.setAttr('type', 'chat')
        client.send(message)

        time.sleep(1)   # some older servers will not send the message if you disconnect immediately after sending
        client.disconnect()

register_plugin(OutputNotifyXmpp, 'notify_xmpp', api_ver=2)
