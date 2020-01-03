import posixpath

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='torrent_files')


class TorrentFiles:
    """Provides content files information when dealing with torrents."""

    @plugin.priority(200)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                files = [
                    posixpath.join(item['path'], item['name'])
                    for item in entry['torrent'].get_filelist()
                ]
                if files:
                    logger.debug('{} files: {}', entry['title'], files)
                    entry['content_files'] = files


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentFiles, 'torrent_files', builtin=True, api_ver=2)
