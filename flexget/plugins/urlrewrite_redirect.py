from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('urlrewrite_redirect')


class UrlRewriteRedirect(object):
    """Rewrites urls which actually redirect somewhere else."""
    def __init__(self):
        self.processed = set()

    def on_task_start(self):
        self.processed = set()

    def url_rewritable(self, task, entry):
        if not any(entry['url'].startswith(adapter) for adapter in task.requests.adapters):
            return False
        return entry['url'] not in self.processed

    def url_rewrite(self, task, entry):
        # Don't accidentally go online in unit tests
        if not task.manager.unit_test:
            auth = None
            if 'download_auth' in entry:
                auth = entry['download_auth']
                log.debug('Custom auth enabled for %s url_redirect: %s' % (entry['title'], entry['download_auth']))
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
    plugin.register(UrlRewriteRedirect, 'urlrewrite_redirect', groups=['urlrewriter'], api_ver=2)
