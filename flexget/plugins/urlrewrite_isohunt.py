import logging
from flexget.plugin import *

log = logging.getLogger("isohunt")


class UrlRewriteIsoHunt:
    """IsoHunt urlrewriter."""

    def url_rewritable(self, feed, entry):
        url = entry['url']
        # search is not supported
        if url.startswith('http://isohunt.com/torrents/?ihq='):
            return False
        # not replaceable
        if not 'torrent_details' in url:
            return False
        return url.startswith('http://isohunt.com') and url.find('download') == -1
        
    def url_rewrite(self, feed, entry):
        entry['url'] = entry['url'].replace('torrent_details', 'download')

register_plugin(UrlRewriteIsoHunt, 'isohunt', groups=['urlrewriter'])
