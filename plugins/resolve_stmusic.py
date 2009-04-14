import logging



log = logging.getLogger("stmusic")

class ResolveSTMusic:
    """STMusic resolver."""

    def register(self, manager, parser):
        manager.register('stmusic', group='resolver')

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.stmusic.org/details.php?id=')

    def resolve(self, feed, entry):
        import urllib
        entry['url'] = entry['url'].replace('details.php?id=', 'download.php/')
        entry['url'] = entry['url'] + '/%s.torrent' % (urllib.quote(entry['title'], safe=''))