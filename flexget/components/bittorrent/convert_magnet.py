from __future__ import annotations

import time
from typing import TYPE_CHECKING
from urllib.parse import quote

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import parse_timedelta

if TYPE_CHECKING:
    from pathlib import Path

logger = logger.bind(name='convert_magnet')


class ConvertMagnet:
    """Convert magnet only entries to a torrent file."""

    schema = {
        'oneOf': [
            # Allow convert_magnet: no form to turn off plugin altogether
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'timeout': {'type': 'string', 'format': 'interval'},
                    'fail_entry_on_error': {'type': 'boolean'},
                },
                'additionalProperties': False,
            },
        ]
    }

    def magnet_to_torrent(self, magnet_uri, destination_folder: Path, timeout) -> str:
        import libtorrent

        params = libtorrent.parse_magnet_uri(magnet_uri)
        session = libtorrent.session()
        params.url = magnet_uri
        params.save_path = str(destination_folder)
        handle = session.add_torrent(params)
        logger.debug('Acquiring torrent metadata for magnet {}', magnet_uri)
        timeout_value = timeout
        while not handle.status().has_metadata:
            time.sleep(0.1)
            timeout_value -= 0.1
            if timeout_value <= 0:
                raise plugin.PluginError(f'Timed out after {timeout} seconds trying to magnetize')
        logger.debug('Metadata acquired')
        torrent_info = handle.torrent_file()

        # Removing this line of code would also work, by writing the `torrent_info` to the
        # existing `params`. A new `params` is created here because the properties in the
        # existing `params` are no longer needed.
        params = libtorrent.add_torrent_params()

        params.ti = torrent_info
        torrent_path = destination_folder / (torrent_info.name() + '.torrent')
        torrent_path.write_bytes(libtorrent.bencode(libtorrent.write_torrent_file(params)))
        logger.debug('Torrent file wrote to {}', torrent_path)
        return str(torrent_path)

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {}
        config.setdefault('timeout', '30 seconds')
        config.setdefault('fail_entry_on_error', False)
        return config

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_start(self, task, config):
        if config is False:
            return
        try:
            import libtorrent  # noqa: F401
        except ImportError:
            raise plugin.DependencyError(
                'convert_magnet', 'libtorrent', 'libtorrent package required', logger
            )

    @plugin.priority(130)
    def on_task_download(self, task, config):
        if config is False:
            return
        config = self.prepare_config(config)
        # Create the conversion target directory
        converted_path = task.manager.config_base / 'converted'

        timeout = parse_timedelta(config['timeout']).total_seconds()

        if not converted_path.is_dir():
            converted_path.mkdir()

        for entry in task.accepted:
            if entry['url'].startswith('magnet:'):
                entry.setdefault('urls', [entry['url']])
                try:
                    logger.info('Converting entry {} magnet URI to a torrent file', entry['title'])
                    torrent_file = self.magnet_to_torrent(entry['url'], converted_path, timeout)
                except plugin.PluginError as e:
                    logger.error(
                        'Unable to convert Magnet URI for entry {}: {}', entry['title'], e
                    )
                    if config['fail_entry_on_error']:
                        entry.fail('Magnet URI conversion failed')
                    continue
                # Windows paths need an extra / prepended to them for url
                if not torrent_file.startswith('/'):
                    torrent_file = '/' + torrent_file
                entry['url'] = torrent_file
                entry['file'] = torrent_file
                # make sure it's first in the list because of how download plugin works
                entry['urls'].insert(0, f'file://{quote(torrent_file)}')


@event('plugin.register')
def register_plugin():
    plugin.register(ConvertMagnet, 'convert_magnet', api_ver=2)
