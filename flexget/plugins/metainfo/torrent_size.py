from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('torrent_size')


class TorrentSize(object):
    """
    Provides file size information when dealing with torrents
    """

    @plugin.priority(200)
    def on_task_modify(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                size = entry['torrent'].size / 1024 / 1024
                log.debug('%s size: %s MB' % (entry['title'], size))
                entry['content_size'] = size


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentSize, 'torrent_size', builtin=True, api_ver=2)
