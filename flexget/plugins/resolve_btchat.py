import logging



log = logging.getLogger("btchat")

class ResolveBtJunkie:
    """BtChat resolver."""

    __plugin__ = 'btchat'
    __plugin_groups__ = ['resolver']

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.bt-chat.com/download.php')
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('download.php', 'download1.php')
