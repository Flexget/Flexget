import logging

log = logging.getLogger("demonoid")

class ResolveDemonoid:
    """Demonoid resolver."""

    __plugin__ = 'demonoid'
    __plugin_groups__ = ['resolver']

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.demonoid.com/files/details/')

    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('details', 'download/HTTP')
