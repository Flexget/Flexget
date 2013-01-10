from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin

log = logging.getLogger('anirena')


class UrlRewriteAniRena:
    """AniRena urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://www.anirena.com/viewtracker.php?action=details&id=')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('details', 'download')

register_plugin(UrlRewriteAniRena, 'anirena', groups=['urlrewriter'])
