import logging
from flexget.plugin import *

log = logging.getLogger("demonoid")


class UrlRewriteDemonoid:
    """Demonoid urlrewriter."""

    def url_rewritable(self, feed, entry):
        return entry['url'].startswith('http://www.demonoid.com/files/details/')

    def url_rewrite(self, feed, entry):
        entry['url'] = entry['url'].replace('details', 'download/HTTP')

register_plugin(UrlRewriteDemonoid, 'demonoid', groups=['urlrewriter'])
