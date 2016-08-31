from __future__ import unicode_literals, division, absolute_import
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
            # Allow retry_failed: no form to turn off plugin altogether
            {"type": "boolean"},
            {
                "type": "object",
                "properties": {
                    "timeout": {"type": "string", "format": "interval", "default": "30 seconds"},
                },
                "additionalProperties": False
            }
        ]
    }

    def magnet_to_torrent(self, magnet_uri, destination_folder, timeout=60):
        import libtorrent
        params = libtorrent.parse_magnet_uri(magnet_uri)
        session = libtorrent.session()
        handle = session.add_torrent(params)
        log.debug('Acquiring torrent metadata for magnet {}'.format(magnet_uri))
        timeout_value = timeout
        while not handle.has_metadata():
            time.sleep(0.1)
            timeout_value -= 0.1
            if timeout_value <= 0:
                raise Exception('Timed out after {} seconds acquiring torrent metadata from the DHT/trackers.'.format(
                    timeout
                ))
        log.debug('Metadata acquired')
        torrent_info = handle.get_torrent_info()
        torrent_file = libtorrent.create_torrent(torrent_info)
        torrent_path = pathscrub(os.path.join(destination_folder, torrent_info.name() + ".torrent"))
        with open(torrent_path, "wb") as f:
            f.write(libtorrent.bencode(torrent_file.generate()))
        log.debug('Torrent file wrote to {}'.format(torrent_path))
        return torrent_path

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {}
        config.setdefault('timeout', '30 seconds')
        return config

    def on_task_start(self, task, config):
        if config is False:
            return
        try:
            import libtorrent
        except ImportError:
            raise plugin.DependencyError('convert_magnet', 'libtorrent', 'libtorrent package required', log)

    @plugin.priority(130)
    def on_task_urlrewrite(self, task, config):
        if config is False:
            return
        # Create the conversion target directory
        converted_path = os.path.join(task.manager.config_base, 'converted')
        # Calculate the timeout config in seconds (Py2.6 compatible, can be replaced with total_seconds in 2.7)
        timeout = 60
        if config and isinstance(config, dict):
            timeout_delta = parse_timedelta(config['timeout'])
            timeout = (timeout_delta.seconds + timeout_delta.days * 24 * 3600)
        if not os.path.isdir(converted_path):
            os.mkdir(converted_path)

        for entry in task.accepted:
            if entry['url'].startswith('magnet:'):
                entry.setdefault('urls', [entry['url']])
                try:
                    log.info('Converting entry {} magnet URI to a torrent file'.format(entry['title']))
                    torrent_file = self.magnet_to_torrent(entry['url'], converted_path, timeout)
                except BaseException as e:
                    message = 'Unable to convert Magnet URI for entry {}: {}'.format(entry['title'], e)
                    log.error(message)
                    continue
                # Windows paths need an extra / prepended to them for url
                if not torrent_file.startswith('/'):
                    torrent_file = '/' + torrent_file
                entry['url'] = torrent_file
                entry['urls'].append('file://{}'.format(torrent_file))


@event('plugin.register')
def register_plugin():
    plugin.register(ConvertMagnet, 'convert_magnet', api_ver=2)


