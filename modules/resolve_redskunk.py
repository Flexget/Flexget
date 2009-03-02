import logging

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger("redskunk")

class ResolveRedskunk:
    """Redskunk resolver."""

    def register(self, manager, parser):
        manager.register('redskunk', group='resolver')

    def resolvable(self, feed, entry):
        url = entry['url']
        return url.startswith('http://redskunk.org') and url.find('download') == -1

    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('torrents-details', 'download')
        entry['url'] = entry['url'].replace('&hit=1', '')
