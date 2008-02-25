import logging

log = logging.getLogger("isohunt")

class ResolveBtJunkie:
    """BtJunkie resolver."""

    def register(self, manager, parser):
        manager.register_resolver(instance=self, resolvable=self.resolvable, resolve=self.resolve)

    def resolvable(self, feed, entry):
        url = entry['url']
        if url.startswith('http://btjunkie.org'):
            return True
        else:
            return False
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('btjunkie.org', 'dl.btjunkie.org')
        entry['url'] = entry['url'] + "/download.torrent"
        return True
