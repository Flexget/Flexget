import logging



log = logging.getLogger("isohunt")

class ResolveIsoHunt:
    """IsoHunt resolver."""

    __plugin__ = 'isohunt'
    __plugin_groups__ = ['resolver']

    def resolvable(self, feed, entry):
        url = entry['url']
        return url.startswith('http://isohunt.com') and url.find('download') == -1
        
    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('torrent_details', 'download')
