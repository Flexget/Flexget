import logging
from flexget.plugin import *

log = logging.getLogger("nyaa")


class UrlRewriteNyaa:
    """Nyaa urlrewriter."""

    def url_rewritable(self, feed, entry):
        return entry['url'].startswith('http://www.nyaa.eu/?page=torrentinfo&tid=')

    def url_rewrite(self, feed, entry):
        entry['url'] = entry['url'].replace('torrentinfo', 'download')

register_plugin(UrlRewriteNyaa, 'nyaa', groups=['urlrewriter'])
