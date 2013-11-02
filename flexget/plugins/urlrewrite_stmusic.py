from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger("stmusic")


class UrlRewriteSTMusic(object):
    """STMusic urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://www.stmusic.org/details.php?id=')

    def url_rewrite(self, task, entry):
        import urllib
        entry['url'] = entry['url'].replace('details.php?id=', 'download.php/')
        entry['url'] += '/%s.torrent' % (urllib.quote(entry['title'], safe=''))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteSTMusic, 'stmusic', groups=['urlrewriter'], api_ver=2)
