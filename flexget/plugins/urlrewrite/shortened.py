from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlparse

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('shortened')


class UrlRewriteShortened(object):
    """Shortened url rewriter."""

    def url_rewritable(self, task, entry):
        return urlparse(entry['url']).netloc in ['bit.ly', 't.co']

    def url_rewrite(self, task, entry):
        request = task.requests.head(entry['url'], allow_redirects=True)
        entry['url'] = request.url


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteShortened, 'shortened', groups=['urlrewriter'], api_ver=2)
