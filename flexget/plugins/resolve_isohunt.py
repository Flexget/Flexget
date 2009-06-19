import logging
from flexget.plugin import *

log = logging.getLogger("isohunt")

class ResolveIsoHunt:
    """IsoHunt resolver."""

    def resolvable(self, feed, entry):
        url = entry['url']
        return url.startswith('http://isohunt.com') and url.find('download') == -1
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('torrent_details', 'download')

register_plugin(ResolveIsoHunt, 'isohunt', groups=['resolver'])
