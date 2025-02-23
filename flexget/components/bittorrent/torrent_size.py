from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import format_filesize

logger = logger.bind(name='torrent_size')


class TorrentSize:
    """Provide file size information when dealing with torrents."""

    @plugin.priority(200)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                size = entry['torrent'].size
                logger.debug('{} size: {}', entry['title'], format_filesize(size))
                entry['content_size'] = size


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentSize, 'torrent_size', builtin=True, api_ver=2)
