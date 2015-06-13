from __future__ import unicode_literals, division, absolute_import
import logging
import urllib

from flexget import plugin
from flexget.event import event

log = logging.getLogger('cinemageddon')


class UrlRewriteCinemageddon(object):
    """Cinemageddon urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://cinemageddon.net/details.php?id=')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('details.php?id=', 'download.php?id=')
        entry['url'] += '&name=%s.torrent' % (urllib.quote(entry['title'], safe=''))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteCinemageddon, 'cinemageddon', groups=['urlrewriter'], api_ver=2)
