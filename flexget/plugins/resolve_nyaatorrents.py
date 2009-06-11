import logging



log = logging.getLogger("nyaatorrents")

class ResolveNyaaTorrents:
    """NyaaTorrents resolver."""

    __plugin__ = 'nyaatorrents'
    __plugin_groups__ = ['resolver']

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.nyaatorrents.org/?page=torrentinfo&tid=')
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('torrentinfo', 'download')
