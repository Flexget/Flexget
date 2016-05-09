from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from bs4 import BeautifulSoup

from flexget import plugin
from flexget.event import event
from flexget.utils import requests

log = logging.getLogger('nnm-club')


class UrlRewriteNnmClub(object):
    """Nnm-club.me urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://nnm-club.me/forum/viewtopic.php?t=')

    def url_rewrite(self, task, entry):
        try:
            r = task.requests.get(entry['url'])
        except requests.RequestException as e:
            log.error('Error while fetching page: %s' % e)
            entry['url'] = None
            return
        html = r.content
        soup = BeautifulSoup(html)
        links = soup.findAll('a', href=True)
        magnets = [x for x in links if x.get('href').startswith('magnet')]
        if not magnets:
            log.error('There is no magnet links on page (%s)' % entry['url'])
            entry['url'] = None
            return
        entry['url'] = magnets[0]



@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteNnmClub, 'nnm-club', groups=['urlrewriter'], api_ver=2)
