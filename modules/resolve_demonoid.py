import logging

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger("demonoid")

class ResolveDemonoid:
    """Demonoid resolver."""

    def register(self, manager, parser):
        manager.register('resolve_demonoid', group='resolver')

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.demonoid.com/files/details/')

    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('details', 'download/HTTP')
