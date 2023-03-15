from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='redirect_url')


class UrlRewriteRedirect:
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
                logger.debug(
                    'Custom auth enabled for {} url_redirect: {}',
                    entry['title'],
                    entry['download_auth'],
                )

            # Jackett uses redirects to redirect to a magnet: uri, which requests will choke on.
            # Therefore we manually resolve the redirects, rather that letting requests do that for us.
            # Some providers also don't allow the HEAD method, so we use GET here for maximum compatibility.
            url = entry['url']
            while True:
                try:
                    # Use 'stream' to make sure we don't download the content. Do the GET with a context manager
                    # to make sure the connection closes since we aren't getting content.
                    with task.requests.get(
                        url, auth=auth, allow_redirects=False, stream=True
                    ) as r:
                        if 'location' in r.headers and 300 <= r.status_code < 400:
                            url = r.headers['location']
                except Exception:
                    break
                if url != r.url:
                    continue
                break
            if url != entry['url']:
                entry['url'] = url
            # Make sure we don't try to rewrite this url again
            self.processed.add(entry['url'])


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteRedirect, 'redirect_url', api_ver=2)
