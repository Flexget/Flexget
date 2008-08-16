import logging

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger("nyaatorrents")

class ResolveNyaaTorrents:
    """NyaaTorrents resolver."""

    def register(self, manager, parser):
        manager.register('resolve_nyaatorrents', group='resolver')

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.nyaatorrents.org/?page=torrentinfo&tid=')
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('torrentinfo', 'download')
