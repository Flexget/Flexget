import logging
from flexget.plugin import *

log = logging.getLogger("demonoid")

class ResolveDemonoid:
    """Demonoid resolver."""

    def resolvable(self, feed, entry):
        return entry['url'].startswith('http://www.demonoid.com/files/details/')

    def resolve(self, feed, entry):
        entry['url'] = entry['url'].replace('details', 'download/HTTP')

register_plugin(ResolveDemonoid, 'demonoid', groups=['resolver'])
