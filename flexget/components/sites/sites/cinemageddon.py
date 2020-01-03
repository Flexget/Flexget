from urllib.parse import quote

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='cinemageddon')


class UrlRewriteCinemageddon:
    """Cinemageddon urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://cinemageddon.net/details.php?id=')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('details.php?id=', 'download.php?id=')
        entry['url'] += '&name=%s.torrent' % (quote(entry['title'], safe=''))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteCinemageddon, 'cinemageddon', interfaces=['urlrewriter'], api_ver=2)
