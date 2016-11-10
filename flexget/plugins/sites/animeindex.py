from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('animeindex')


# http://tracker.anime-index.org/index.php?page=torrent-details&id=b8327fdf9003e87446c8b3601951a9a65526abb2
# http://tracker.anime-index.org/download.php?id=b8327fdf9003e87446c8b3601951a9a65526abb2&f=[DeadFish]%20Yowamushi%20Pedal:%20Grande%20Road%20-%2002%20[720p][AAC].mp4.torrent


class UrlRewriteAnimeIndex(object):
    """AnimeIndex urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://tracker.anime-index.org/index.php?page=torrent-details&id=')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('index.php?page=torrent-details&', 'download.php?')
        entry['url'] += '&f=%s.torrent' % (quote(entry['title'], safe=''))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteAnimeIndex, 'animeindex', groups=['urlrewriter'], api_ver=2)
