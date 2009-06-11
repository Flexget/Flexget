import logging



log = logging.getLogger("btjunkie")

class ResolveBtJunkie:
    """BtJunkie resolver."""

    __plugin__ = 'btjunkie'
    __plugin_groups__ = ['resolver']

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://btjunkie.org')
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('btjunkie.org', 'dl.btjunkie.org')
        entry['url'] = entry['url'] + "/download.torrent"
