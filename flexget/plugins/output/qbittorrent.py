from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from requests import Session

from flexget import plugin
from flexget.event import event

log = logging.getLogger('qbittorrent')


class OutputQBitTorrent(object):
    """
    Example:

      qbittorrent:
        username: <USERNAME> (default: (none))
        password: <PASSWORD> (default: (none))
        host: <HOSTNAME> (default: localhost)
        port: <PORT> (default: 8080)
        path: <OUTPUT_DIR> (default: (none))
        label: <LABEL> (default: (none))
    """
    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'host': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'path': {'type': 'string'},
                    'label': {'type': 'string'}
                },
                'additionalProperties': False
            }
        ]
    }

    def connect(self, config):
        """
        Connect to qBittorrent Web UI. Username and password not necessary
        if 'Bypass authentication for localhost' is checked and host is
        'localhost'.
        """
        self.session = Session()
        self.url = 'http://{}:{}'.format(config['host'], config['port'])
        if config.get('username') and config.get('password'):
            response = self.session.post(self.url + '/login',
                                         data={'username': config['username'],
                                               'password': config['password']})
            if response == 'Fails.':
                log.debug('Error connecting to qBittorrent')
                raise plugin.PluginError('Authentication failed.')
        log.debug('Successfully connected to qBittorrent')
        self.connected = True

    def add_torrent(self, data):
        if not self.connected:
            raise plugin.PluginError('Not connected.')
        multipart_data = {k: (None, v) for k, v in data.items()}
        self.session.post(self.url + '/command/download', files=multipart_data)
        log.debug('Added task to qBittorrent')

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('enabled', True)
        config.setdefault('host', 'localhost')
        config.setdefault('port', 8080)
        config.setdefault('label', '')
        return config

    @plugin.priority(120)
    def on_task_download(self, task, config):
        """
        Call download plugin to generate torrent files to load into
        qBittorrent.
        """
        config = self.prepare_config(config)
        if not config['enabled']:
            return
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.get_temp_files(task, handle_magnets=True)

    @plugin.priority(135)
    def on_task_output(self, task, config):
        """Add torrents to qBittorrent at exit."""
        if task.accepted:
            config = self.prepare_config(config)
            self.connect(config)
        for entry in task.accepted:
            data = {}
            savepath = entry.get('path', config.get('path'))
            if savepath:
                data['savepath'] = savepath
            label = entry.get('label', config['label']).lower()
            if label:
                data['label'] = label
            data['urls'] = entry.get('url')
            if task.manager.options.test:
                log.info('Test mode.')
                log.info('Would add torrent to qBittorrent with:')
                log.info('    Url: %s', data['urls'][0])
                if data['savepath']:
                    log.info('    Save path: %s', data['savepath'])
                if data['label']:
                    log.info('    Label: %s', data['label'])
            else:
                self.add_torrent(data)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputQBitTorrent, "qbittorrent", api_ver=2)
