from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
import os
import time
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import parse_timedelta
from flexget.utils.pathscrub import pathscrub

log = logging.getLogger('convert_magnet')


class ConvertMagnet(object):
    """Convert magnet only entries to a torrent file"""

    schema = {
        "oneOf": [
            # Allow convert_magnet: no form to turn off plugin altogether
            {"type": "boolean"},
            {
                "type": "object",
                "properties": {
                    "timeout": {"type": "string", "format": "interval"},
                    "force": {"type": "boolean"}
                },
                "additionalProperties": False
            }
        ]
    }

    def magnet_to_torrent(self, magnet_uri, destination_folder, timeout):
        import libtorrent
        params = libtorrent.parse_magnet_uri(magnet_uri)
        session = libtorrent.session()
        lt_version = [int(v) for v in libtorrent.version.split('.')]
        if lt_version > [0,16,13,0] and lt_version < [1,1,3,0]:
            # for some reason the info_hash needs to be bytes but it's a struct called sha1_hash
            params['info_hash'] = params['info_hash'].to_bytes()
        handle = libtorrent.add_magnet_uri(session, magnet_uri, params)
        log.debug('Acquiring torrent metadata for magnet %s', magnet_uri)
        timeout_value = timeout
        while not handle.has_metadata():
            time.sleep(0.1)
            timeout_value -= 0.1
            if timeout_value <= 0:
                raise plugin.PluginError('Timed out after {} seconds trying to magnetize'.format(timeout))
        log.debug('Metadata acquired')
        torrent_info = handle.get_torrent_info()
        torrent_file = libtorrent.create_torrent(torrent_info)
        torrent_path = pathscrub(os.path.join(destination_folder, torrent_info.name() + ".torrent"))
        with open(torrent_path, "wb") as f:
            f.write(libtorrent.bencode(torrent_file.generate()))
        log.debug('Torrent file wrote to %s', torrent_path)
        return torrent_path

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {}
        config.setdefault('timeout', '30 seconds')
        config.setdefault('force', False)
        return config

    @plugin.priority(255)
    def on_task_start(self, task, config):
        if config is False:
            return
        try:
            import libtorrent  # noqa
        except ImportError:
            raise plugin.DependencyError('convert_magnet', 'libtorrent', 'libtorrent package required', log)

    @plugin.priority(130)
    def on_task_download(self, task, config):
        if config is False:
            return
        config = self.prepare_config(config)
        # Create the conversion target directory
        converted_path = os.path.join(task.manager.config_base, 'converted')

        timeout = parse_timedelta(config['timeout']).total_seconds()

        if not os.path.isdir(converted_path):
            os.mkdir(converted_path)

        for entry in task.accepted:
            if entry['url'].startswith('magnet:'):
                entry.setdefault('urls', [entry['url']])
                try:
                    log.info('Converting entry {} magnet URI to a torrent file'.format(entry['title']))
                    torrent_file = self.magnet_to_torrent(entry['url'], converted_path, timeout)
                except (plugin.PluginError, TypeError) as e:
                    log.error('Unable to convert Magnet URI for entry %s: %s', entry['title'], e)
                    if config['force']:
                        entry.fail('Magnet URI conversion failed')
                    continue
                # Windows paths need an extra / prepended to them for url
                if not torrent_file.startswith('/'):
                    torrent_file = '/' + torrent_file
                entry['url'] = torrent_file
                entry['file'] = torrent_file
                # make sure it's first in the list because of how download plugin works
                entry['urls'].insert(0, 'file://{}'.format(torrent_file))


@event('plugin.register')
def register_plugin():
    plugin.register(ConvertMagnet, 'convert_magnet', api_ver=2)
