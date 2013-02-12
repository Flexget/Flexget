from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin

log = logging.getLogger("btjunkie")


class UrlRewriteBtJunkie:
    """BtJunkie urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://btjunkie.org')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('btjunkie.org', 'dl.btjunkie.org')
        entry['url'] = entry['url'] + "/download.torrent"

register_plugin(UrlRewriteBtJunkie, 'btjunkie', groups=['urlrewriter'])
