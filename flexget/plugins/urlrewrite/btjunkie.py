from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger("btjunkie")


class UrlRewriteBtJunkie(object):
    """BtJunkie urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://btjunkie.org')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('btjunkie.org', 'dl.btjunkie.org')
        entry['url'] += "/download.torrent"


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteBtJunkie, 'btjunkie', groups=['urlrewriter'], api_ver=2)
