from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import priority, register_plugin

log = logging.getLogger('torrent_size')


class TorrentSize(object):
    """
    Provides file size information when dealing with torrents
    """

    @priority(200)
    def on_task_modify(self, task):
        for entry in task.entries:
            if 'torrent' in entry:
                size = entry['torrent'].size / 1024 / 1024
                log.debug('%s size: %s MB' % (entry['title'], size))
                entry['content_size'] = size


register_plugin(TorrentSize, 'torrent_size', builtin=True)
