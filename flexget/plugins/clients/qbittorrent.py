from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import os
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
                    'label': {'type': 'string'},
                    'fail_html': {'type': 'boolean'}
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

    def add_torrent_file(self, filepath, data):
        if not self.connected:
            raise plugin.PluginError('Not connected.')
        multipart_data = {k: (None, v) for k, v in data.items()}
        with open(filepath, 'rb') as f:
            multipart_data['torrents'] = f
            self.session.post(self.url + '/command/upload', files=multipart_data)
        log.debug('Added torrent file %s to qBittorrent', filepath)

    def add_torrent_url(self, url, data):
        if not self.connected:
            raise plugin.PluginError('Not connected.')
        data['urls'] = url
        multipart_data = {k: (None, v) for k, v in data.items()}
        self.session.post(self.url + '/command/download', files=multipart_data)
        log.debug('Added url %s to qBittorrent', url)

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('enabled', True)
        config.setdefault('host', 'localhost')
        config.setdefault('port', 8080)
        config.setdefault('label', '')
        config.setdefault('fail_html', True)
        return config

    def add_entries(self, task, config):
        for entry in task.accepted:
            formdata = {}

            savepath = entry.get('path', config.get('path'))
            if savepath:
                formdata['savepath'] = savepath

            label = entry.get('label', config.get('label'))
            if label:
                formdata['label'] = label # qBittorrent v3.3.3-
                formdata['category'] = label # qBittorrent v3.3.4+

            is_magnet = entry['url'].startswith('magnet:')

            if task.manager.options.test:
                log.info('Test mode.')
                log.info('Would add torrent to qBittorrent with:')
                if not is_magnet:
                    log.info('File: %s', entry.get('file'))
                else:
                    log.info('Url: %s', entry.get('url'))
                log.info('Save path: %s', formdata.get('savepath'))
                log.info('Label: %s', formdata.get('label'))
                continue

            if not is_magnet:
                if 'file' not in entry:
                    entry.fail('File missing?')
                    continue
                if not os.path.exists(entry['file']):
                    tmp_path = os.path.join(task.manager.config_base, 'temp')
                    log.debug('entry: %s', entry)
                    log.debug('temp: %s', ', '.join(os.listdir(tmp_path)))
                    entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
                    continue
                self.add_torrent_file(entry['file'], formdata)
            else:
                self.add_torrent_url(entry['url'], formdata)

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
            download.instance.get_temp_files(task, handle_magnets=True, fail_html=config['fail_html'])

    @plugin.priority(135)
    def on_task_output(self, task, config):
        """Add torrents to qBittorrent at exit."""
        if task.accepted:
            config = self.prepare_config(config)
            self.connect(config)
            self.add_entries(task, config)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputQBitTorrent, "qbittorrent", api_ver=2)
