from __future__ import unicode_literals, division, absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import object
import logging
import urllib.request, urllib.parse, urllib.error

from flexget import plugin
from flexget.event import event

log = logging.getLogger('cinemageddon')


class UrlRewriteCinemageddon(object):
    """Cinemageddon urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://cinemageddon.net/details.php?id=')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('details.php?id=', 'download.php?id=')
        entry['url'] += '&name=%s.torrent' % (urllib.parse.quote(entry['title'], safe=''))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteCinemageddon, 'cinemageddon', groups=['urlrewriter'], api_ver=2)
