from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import posixpath

from flexget import plugin
from flexget.event import event

log = logging.getLogger('torrent_files')


class TorrentFiles(object):
    """Provides content files information when dealing with torrents."""

    @plugin.priority(200)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                files = [posixpath.join(item['path'], item['name']) for item in entry['torrent'].get_filelist()]
                if files:
                    log.debug('%s files: %s' % (entry['title'], files))
                    entry['content_files'] = files


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentFiles, 'torrent_files', builtin=True, api_ver=2)
