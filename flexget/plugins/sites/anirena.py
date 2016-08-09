from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('anirena')


class UrlRewriteAniRena(object):
    """AniRena urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://www.anirena.com/viewtracker.php?action=details&id=')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('details', 'download')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteAniRena, 'anirena', groups=['urlrewriter'], api_ver=2)
