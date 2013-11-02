from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger("btchat")


class UrlRewriteBtChat(object):
    """BtChat urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://www.bt-chat.com/download.php')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('download.php', 'download1.php')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteBtChat, 'btchat', groups=['urlrewriter'], api_ver=2)
