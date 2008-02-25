import logging

log = logging.getLogger("torrentspy")

class ResolveTorrentSpy:
    """TorrentSpy resolver."""

    def register(self, manager, parser):
        manager.register_resolver(instance=self, name='torrentspy')

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.torrentspy.com/torrent/')
        
    def resolve(self, feed, entry):
        import re
        m = re.match('http://www.torrentspy.com/torrent/([\d]+)/', entry['url'])
        torrent_id = m.group(1)
        entry['url'] = 'http://www.torrentspy.com/download.asp?id=%s' % torrent_id
        return True
