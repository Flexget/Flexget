import base64
import re

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='magnet_btih')


class MagnetBtih:
    """Sets torrent_info_hash from magnet url."""

    schema = {'type': 'boolean'}

    def on_task_metainfo(self, task, config):
        if config is False:
            return
        for entry in task.all_entries:
            if entry.get('torrent_info_hash'):
                continue
            for url in [entry['url'], *entry.get('urls', [])]:
                if url.startswith('magnet:'):
                    # find base16 encoded
                    info_hash_search = re.search('btih:([0-9a-f]{40})', url, re.IGNORECASE)
                    if info_hash_search:
                        entry['torrent_info_hash'] = info_hash_search.group(1).upper()
                        break
                    # find base32 encoded
                    info_hash_search = re.search('btih:([2-7a-z]{32})', url, re.IGNORECASE)
                    if info_hash_search:
                        b32hash = info_hash_search.group(1).upper()
                        b16hash = base64.b16encode(base64.b32decode(b32hash))
                        entry['torrent_info_hash'] = b16hash.decode('ascii').upper()
                        break


@event('plugin.register')
def register_plugin():
    plugin.register(MagnetBtih, 'magnet_btih', builtin=True, api_ver=2)
