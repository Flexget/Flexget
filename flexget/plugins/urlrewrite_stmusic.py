import logging
from flexget.plugin import *

log = logging.getLogger("stmusic")

class UrlRewriteSTMusic:
    """STMusic urlrewriter."""

    def url_rewritable(self, feed, entry):
        return entry['url'].startswith('http://www.stmusic.org/details.php?id=')

    def url_rewrite(self, feed, entry):
        import urllib
        entry['url'] = entry['url'].replace('details.php?id=', 'download.php/')
        entry['url'] = entry['url'] + '/%s.torrent' % (urllib.quote(entry['title'], safe=''))

register_plugin(UrlRewriteSTMusic, 'stmusic', groups=['urlrewriter'])
