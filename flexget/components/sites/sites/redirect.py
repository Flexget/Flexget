from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('redirect_url')


class UrlRewriteRedirect(object):
    """Rewrites urls which actually redirect somewhere else."""

    def __init__(self):
        self.processed = set()

    def on_task_start(self, task, config):
        self.processed = set()

    def on_task_urlrewrite(self, task, config):
        if not config:
            return
        for entry in task.accepted:
            if not any(entry['url'].startswith(adapter) for adapter in task.requests.adapters):
                continue
            elif entry['url'] in self.processed:
                continue
            auth = None
            if 'download_auth' in entry:
                auth = entry['download_auth']
                log.debug(
                    'Custom auth enabled for %s url_redirect: %s'
                    % (entry['title'], entry['download_auth'])
                )
            try:
                r = task.requests.head(entry['url'], auth=auth, allow_redirects=True)
            except Exception:
                pass
            else:
                if r.status_code < 400 and r.url != entry['url']:
                    entry['url'] = r.url
            # Make sure we don't try to rewrite this url again
            self.processed.add(entry['url'])


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteRedirect, 'redirect_url', api_ver=2)
