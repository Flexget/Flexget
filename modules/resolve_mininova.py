import logging

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger("mininova")

class ResolveMininova:
    """Mininova resolver."""

    def register(self, manager, parser):
        manager.register_resolver(instance=self, name='mininova')

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.mininova.org/tor/')
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('tor', 'get')
