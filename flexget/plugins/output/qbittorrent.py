from __future__ import unicode_literals, division, absolute_import

import logging

from qbittorrent import Client

from flexget import plugin
from flexget.event import event

log = logging.getLogger('qbittorrent')

class OutputQBitTorrent(object):
    """
    Example:

      qbittorrent:
        username: <USERNAME>
        password: <PASSWORD>
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
        },
        'required': ['username', 'password']
    }

    def connect(self, config):
        qb = Client('http://{}:{}'.format(config['host'], config['port']))
        response = qb.login(config['username'], config['password'])
        if response == 'Fails.':
            raise plugin.PluginError('Authentication failed.')
        return qb

    def prepare_config(self, config):
        config.setdefault('host', 'localhost')
        config.setdefault('port', 8080)
        config.setdefault('label', '')
        return config

    @plugin.priority(120)
    def on_task_output(self, task, config):
        """Add torrents to qbittorrent at exit."""
        if task.accepted:
            config = self.prepare_config(config)
            qb = self.connect(config)
        for entry in task.accepted:
            data = {}
            data['save_path'] = entry.get('movedone', config.get('movedone'))
            data['label'] = entry.get('label', config['label']).lower()
            url = entry.get('url')
            qb.download_from_link(url, **data)

@event('plugin.register')
def register_plugin():
    plugin.register(OutputQBitTorrent, "qbittorrent", api_ver=2)
