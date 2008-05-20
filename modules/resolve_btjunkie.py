import logging

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger("btjunkie")

class ResolveBtJunkie:
    """BtJunkie resolver."""

    def register(self, manager, parser):
        manager.register_resolver(name='btjunkie')

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://btjunkie.org')
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('btjunkie.org', 'dl.btjunkie.org')
        entry['url'] = entry['url'] + "/download.torrent"
