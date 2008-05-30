import logging

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger("elite-team")

class ResolveEliteTeam:
    """Elite-Team resolver."""

    def register(self, manager, parser):
        manager.register_resolver(instance=self, name='elite-team')

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.elite-team.net/tracker/torrents-details')

    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('torrents-details', 'download')
