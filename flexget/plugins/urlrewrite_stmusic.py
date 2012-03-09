import logging
from flexget.plugin import register_plugin

log = logging.getLogger("stmusic")


class UrlRewriteSTMusic(object):
    """STMusic urlrewriter."""

    def url_rewritable(self, feed, entry):
        return entry['url'].startswith('http://www.stmusic.org/details.php?id=')

    def url_rewrite(self, feed, entry):
        import urllib
        entry['url'] = entry['url'].replace('details.php?id=', 'download.php/')
        entry['url'] += '/%s.torrent' % (urllib.quote(entry['title'], safe=''))

register_plugin(UrlRewriteSTMusic, 'stmusic', groups=['urlrewriter'])
