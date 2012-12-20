from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin

log = logging.getLogger("redskunk")


class UrlRewriteRedskunk(object):
    """Redskunk urlrewriter."""

    def url_rewritable(self, task, entry):
        url = entry['url']
        return url.startswith('http://redskunk.org') and url.find('download') == -1

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('torrents-details', 'download')
        entry['url'] = entry['url'].replace('&hit=1', '')

register_plugin(UrlRewriteRedskunk, 'redskunk', groups=['urlrewriter'])
