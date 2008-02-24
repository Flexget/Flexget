import logging

log = logging.getLogger("isohunt")

class ResolveIsoHunt:
    """IsoHunt resolver."""

    def register(self, manager, parser):
        manager.register_resolver(instance=self, resolvable=self.resolvable, resolve=self.resolve)

    def resolvable(self, feed, entry):
        url = entry['url']
        if url.startswith('http://isohunt.com') and url.find('download') != -1:
            return True
        else:
            return False
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('torrent_details', 'download')
        return True
