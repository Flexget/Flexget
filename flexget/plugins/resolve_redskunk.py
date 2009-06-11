import logging



log = logging.getLogger("redskunk")

class ResolveRedskunk:
    """Redskunk resolver."""

    __plugin__ = 'redskunk'
    __plugin_groups__ = ['resolver']

    def resolvable(self, feed, entry):
        url = entry['url']
        return url.startswith('http://redskunk.org') and url.find('download') == -1

    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('torrents-details', 'download')
        entry['url'] = entry['url'].replace('&hit=1', '')
