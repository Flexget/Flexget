from __future__ import unicode_literals, division, absolute_import

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
        movedone: <OUTPUT_DIR> (default: (none))
        label: <LABEL> (default: (none))
    """
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'host': {'type': 'string'},
            'port': {'type': 'integer'},
            'movedone': {'type': 'string'},
            'label': {'type': 'string'}
        }
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
        self.session.post(self.url + '/command/download', data=data)
        log.debug('Added task to qBittorrent')

    def prepare_config(self, config):
        config.setdefault('host', 'localhost')
        config.setdefault('port', 8080)
        config.setdefault('label', '')
        return config

    @plugin.priority(120)
    def on_task_output(self, task, config):
        """Add torrents to qBittorrent at exit."""
        if task.accepted:
            config = self.prepare_config(config)
            self.connect(config)
        for entry in task.accepted:
            data = {}
            data['savepath'] = entry.get('movedone', config.get('movedone'))
            data['label'] = entry.get('label', config['label']).lower()
            data['urls'] = [entry.get('url')]
            self.add_torrent(data)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputQBitTorrent, "qbittorrent", api_ver=2)
