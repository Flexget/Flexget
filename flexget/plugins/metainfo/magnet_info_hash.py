from __future__ import unicode_literals, division, absolute_import
import logging
import re

from flexget import plugin
from flexget.event import event

log = logging.getLogger('modify_magnet_btih')


class MagnetInfoHash(object):
    """Sets torrent_info_hash from magnet url."""

    schema = {'type': 'boolean'}

    def on_task_metainfo(self, task, config):
        if config is False:
            return
        for entry in task.all_entries:
            for url in [entry['url']] + entry.get('urls', []):
                if url.startswith('magnet:'):
                    info_hash_search = re.search('btih:([0-9a-f]+)', url, re.IGNORECASE)
                    if info_hash_search and not entry.get('torrent_info_hash'):
                        entry['torrent_info_hash'] = info_hash_search.group(1).upper()


@event('plugin.register')
def register_plugin():
    plugin.register(MagnetInfoHash, 'magnet_info_hash', builtin=True, api_ver=2)
