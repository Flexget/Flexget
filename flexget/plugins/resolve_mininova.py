import logging
from flexget.plugin import *

log = logging.getLogger("mininova")

class ResolveMininova:
    """Mininova resolver."""

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.mininova.org/tor/')
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('tor', 'get')

register_plugin(ResolveMininova, 'mininova', groups=['resolver'])
