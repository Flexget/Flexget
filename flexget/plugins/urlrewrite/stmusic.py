from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger("stmusic")


class UrlRewriteSTMusic(object):
    """STMusic urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://www.stmusic.org/details.php?id=')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('details.php?id=', 'download.php/')
        entry['url'] += '/%s.torrent' % (quote(entry['title'], safe=''))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteSTMusic, 'stmusic', groups=['urlrewriter'], api_ver=2)
