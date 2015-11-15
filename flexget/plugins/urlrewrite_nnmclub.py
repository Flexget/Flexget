from __future__ import unicode_literals, division, absolute_import
import logging

from bs4 import BeautifulSoup

from flexget import plugin
from flexget.event import event

log = logging.getLogger('nnm-club')


class UrlRewriteNnmClub(object):
    """Nnm-club.me urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://nnm-club.me/forum/viewtopic.php?t=')

    def url_rewrite(self, task, entry):
        html = task.requests.get(entry['url']).content
        soup = BeautifulSoup(html)
        links = soup.findAll('a', href=True)
        magnets = filter(lambda x: x.get('href').startswith('magnet'), links)
        entry['url'] = magnets[0] if magnets else None



@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteNnmClub, 'nnm-club', groups=['urlrewriter'], api_ver=2)
