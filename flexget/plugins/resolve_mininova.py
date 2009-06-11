import logging

log = logging.getLogger("mininova")

class ResolveMininova:
    """Mininova resolver."""

    __plugin__ = 'mininova'
    __plugin_groups__ = ['resolver']

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.mininova.org/tor/')
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('tor', 'get')
