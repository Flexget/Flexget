from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import os

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('deluge3')


class DelugePlugin(object):
    """Base class for deluge plugins, contains settings and methods for connecting to a deluge daemon."""

    def on_task_start(self, task, config):
        """Raise a DependencyError if our dependencies aren't available"""
        try:
            from deluge_client import DelugeRPCClient
        except ImportError as e:
            log.debug('Error importing deluge-client: %s' % e)
            raise plugin.DependencyError('deluge', 'deluge-client',
                                         'deluge-client >=1.2 module and it\'s dependencies required. ImportError: %s' %
                                         e, log)
        self.client = DelugeRPCClient(config['host'], config['port'], config['username'], config['password'],
                                      decode_utf8=True)

    def on_task_abort(self, task, config):
        pass

    def prepare_connection_info(self, config):
        config.setdefault('host', 'localhost')
        config.setdefault('port', 58846)

    def connect(self):
        """Connects to the deluge daemon and runs on_connect_success """

        self.client.connect()

        if not self.client.connected:
            raise plugin.PluginError('Deluge failed to connect.')

    def disconnect(self):
        self.client.disconnect()

    def get_torrents_status(self, fields, filters=None):
        """Fetches all torrents and their requested fields optionally filtered"""
        if filters is None:
            filters = {}
        return self.client.call('core.get_torrents_status', filters, fields)


class InputDeluge(DelugePlugin):
    """Create entries for torrents in the deluge session."""
    #
    settings_map = {
        'name': 'title',
        'hash': 'torrent_info_hash',
        'num_peers': 'torrent_peers',
        'num_seeds': 'torrent_seeds',
        'progress': 'deluge_progress',
        'seeding_time': ('deluge_seed_time', lambda time: time / 3600),
        'private': 'deluge_private',
        'state': 'deluge_state',
        'eta': 'deluge_eta',
        'ratio': 'deluge_ratio',
        'move_on_completed_path': 'deluge_movedone',
        'save_path': 'deluge_path',
        'label': 'deluge_label',
        'total_size': ('content_size', lambda size: size / 1024 / 1024),
        'files': ('content_files', lambda file_dicts: [f['path'] for f in file_dicts])}

    extra_settings_map = {
        'active_time': ('active_time', lambda time: time / 3600),
        'compact': 'compact',
        'distributed_copies': 'distributed_copies',
        'download_payload_rate': 'download_payload_rate',
        'file_progress': 'file_progress',
        'is_auto_managed': 'is_auto_managed',
        'is_seed': 'is_seed',
        'max_connections': 'max_connections',
        'max_download_speed': 'max_download_speed',
        'max_upload_slots': 'max_upload_slots',
        'max_upload_speed':  'max_upload_speed',
        'message': 'message',
        'move_on_completed': 'move_on_completed',
        'next_announce': 'next_announce',
        'num_files': 'num_files',
        'num_pieces': 'num_pieces',
        'paused': 'paused',
        'peers': 'peers',
        'piece_length': 'piece_length',
        'prioritize_first_last': 'prioritize_first_last',
        'queue': 'queue',
        'remove_at_ratio': 'remove_at_ratio',
        'seed_rank': 'seed_rank',
        'stop_at_ratio': 'stop_at_ratio',
        'stop_ratio': 'stop_ratio',
        'total_done': 'total_done',
        'total_payload_download': 'total_payload_download',
        'total_payload_upload': 'total_payload_upload',
        'total_peers': 'total_peers',
        'total_seeds': 'total_seeds',
        'total_uploaded': 'total_uploaded',
        'total_wanted': 'total_wanted',
        'tracker': 'tracker',
        'tracker_host': 'tracker_host',
        'tracker_status': 'tracker_status',
        'trackers': 'trackers',
        'upload_payload_rate': 'upload_payload_rate'
    }

    def __init__(self):
        self.entries = []

    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'host': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'config_path': {'type': 'string', 'format': 'path'},
                    'filter': {
                        'type': 'object',
                        'properties': {
                            'label': {'type': 'string'},
                            'state': {
                                'type': 'string',
                                'enum': ['active', 'downloading', 'seeding', 'queued', 'paused']
                            }
                        },
                        'additionalProperties': False
                    },
                    'keys': {
                        'type': 'array',
                        'items': {
                            'type': 'string',
                            'enum': list(extra_settings_map)
                        }
                    }
                },
                'additionalProperties': False
            }
        ]
    }

    def on_task_start(self, task, config):
        config = self.prepare_config(config)
        super(InputDeluge, self).on_task_start(task, config)

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {}
        if 'filter' in config:
            filter = config['filter']
            if 'label' in filter:
                filter['label'] = filter['label'].lower()
            if 'state' in filter:
                filter['state'] = filter['state'].capitalize()
        self.prepare_connection_info(config)
        return config

    def on_task_input(self, task, config):
        """Generates and returns a list of entries from the deluge daemon."""
        # Reset the entries list
        self.entries = []
        # Call connect, entries get generated if everything is successful
        self.connect()

        self.entries = self.generate_entries(config)
        self.disconnect()
        return self.entries

    def generate_entries(self, config):
        entries = []
        torrents = self.get_torrents_status(list(self.settings_map.keys()) + config.get('keys', []))
        for hash, torrent_dict in torrents.items():
            # Make sure it has a url so no plugins crash
            entry = Entry(deluge_id=hash, url='')
            config_path = os.path.expanduser(config.get('config_path', ''))
            if config_path:
                torrent_path = os.path.join(config_path, 'state', hash + '.torrent')
                if os.path.isfile(torrent_path):
                    entry['location'] = torrent_path
                    if not torrent_path.startswith('/'):
                        torrent_path = '/' + torrent_path
                    entry['url'] = 'file://' + torrent_path
                else:
                    log.warning('Did not find torrent file at %s' % torrent_path)
            for key, value in torrent_dict.items():
                if key in self.settings_map:
                    flexget_key = self.settings_map[key]
                else:
                    flexget_key = self.extra_settings_map[key]
                if isinstance(flexget_key, tuple):
                    flexget_key, format_func = flexget_key
                    value = format_func(value)
                entry[flexget_key] = value
            entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputDeluge, 'from_deluge3', api_ver=2)