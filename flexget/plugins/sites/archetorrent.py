from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger("archetorrent")


class UrlRewriteArchetorrent(object):
    """Archetorrent urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        return url.startswith('https://www.archetorrent.com') and url.find('download') == -1

    # urlrewriter API
    def url_rewrite(self, task, entry):
        if 'url' not in entry:
            log.error("Didn't actually get a URL...")
        else:
            log.debug("Got the URL: %s" % entry['url'])
            entry['url'] = entry['url'].replace('torrents-details', 'download')
            entry['url'] = entry['url'].replace('&hit=1', '')
            log.debug("New URL: %s" % entry['url'])


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteArchetorrent, 'archetorrent', interfaces=['urlrewriter'], api_ver=2)
