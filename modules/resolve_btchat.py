import logging

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger("btchat")

class ResolveBtJunkie:
    """BtChat resolver."""

    def register(self, manager, parser):
        manager.register(name='btchat', group='resolver')

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.bt-chat.com/download.php')
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('download.php', 'download1.php')
