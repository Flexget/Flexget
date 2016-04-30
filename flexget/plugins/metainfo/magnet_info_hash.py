from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event

log = logging.getLogger('magnet_btih')


class MagnetBtih(object):
    """Sets torrent_info_hash from magnet url."""

    schema = {'type': 'boolean'}

    def on_task_metainfo(self, task, config):
        if config is False:
            return
        for entry in task.all_entries:
            if entry.get('torrent_info_hash'):
                continue
            for url in [entry['url']] + entry.get('urls', []):
                if url.startswith('magnet:'):
                    info_hash_search = re.search('btih:([0-9a-f]+)', url, re.IGNORECASE)
                    if info_hash_search:
                        entry['torrent_info_hash'] = info_hash_search.group(1).upper()
                        break


@event('plugin.register')
def register_plugin():
    plugin.register(MagnetBtih, 'magnet_btih', builtin=True, api_ver=2)
