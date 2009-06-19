import logging
from flexget.plugin import *

log = logging.getLogger("btchat")

class ResolveBtChat:
    """BtChat resolver."""

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.bt-chat.com/download.php')
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('download.php', 'download1.php')

register_plugin(ResolveBtChat, 'btchat', groups=['resolver'])
