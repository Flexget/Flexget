import logging
from flexget.plugin import *

log = logging.getLogger("nyaatorrents")


class UrlRewriteNyaaTorrents:
    """NyaaTorrents urlrewriter."""

    def url_rewritable(self, feed, entry):
        return entry['url'].startswith('http://www.nyaatorrents.org/?page=torrentinfo&tid=')
        
    def url_rewrite(self, feed, entry):
        entry['url'] = entry['url'].replace('torrentinfo', 'download')

register_plugin(UrlRewriteNyaaTorrents, 'nyaatorrents', groups=['urlrewriter'])
