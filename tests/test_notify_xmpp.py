from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.plugins.attrib import attr

# Not really sure what else to test without a mock XMPP server

class TestNotifyXmpp(FlexGetBase):
    __yaml__ = """
        tasks:
          authentication:
            mock:
              - {title: 'entry 2'}
            accept_all: yes
            notify_xmpp:
              bot_jid: 'flexget@jabber.ccc.de'
              bot_password: 'not the actual password'
              bot_server: 'jabber.ccc.de'
              recipient: '$%(/_faulty@recipient@jabber.org'
      """

    @attr(online=True)
    def test_authentication(self):
        """Notify XMPP: Successfully connect but fail to authenticate"""
        self.execute_task('authentication', True)
        assert self.task._abort_reason == 'Could not authenticate as flexget@jabber.ccc.de'
