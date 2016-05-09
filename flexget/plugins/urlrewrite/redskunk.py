from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger("redskunk")


class UrlRewriteRedskunk(object):
    """Redskunk urlrewriter."""

    def url_rewritable(self, task, entry):
        url = entry['url']
        return url.startswith('http://redskunk.org') and url.find('download') == -1

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('torrents-details', 'download')
        entry['url'] = entry['url'].replace('&hit=1', '')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteRedskunk, 'redskunk', groups=['urlrewriter'], api_ver=2)
