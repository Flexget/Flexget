from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import os
import logging

from requests import Session
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError


log = logging.getLogger('qbittorrent')


class OutputQBitTorrent(object):
    """
    Example:

      qbittorrent:
        username: <USERNAME> (default: (none))
        password: <PASSWORD> (default: (none))
        host: <HOSTNAME> (default: localhost)
        port: <PORT> (default: 8080)
        use_ssl: <SSL> (default: False)
        verify_cert: <VERIFY> (default: True)
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
                    'use_ssl': {'type': 'boolean'},
                    'verify_cert': {'type': 'boolean'},
                    'path': {'type': 'string'},
                    'label': {'type': 'string'},
                    'fail_html': {'type': 'boolean'}
                },
                'additionalProperties': False
            }
        ]
    }

    def _request(self, method, url, msg_on_fail=None, **kwargs):
        try:
            response = self.session.request(method, url, **kwargs)
            if response == 'Fails.':
                msg = 'Failure. URL: {}, data: {}'.format(url, kwargs) if not msg_on_fail else msg_on_fail
            else:
                return response
        except RequestException as e:
            msg = str(e)
        raise plugin.PluginError('Error when trying to send request to qBittorrent: {}'.format(msg))

    def connect(self, config):
        """
        Connect to qBittorrent Web UI. Username and password not necessary
        if 'Bypass authentication for localhost' is checked and host is
        'localhost'.
        """
        self.session = Session()
        self.url = '{}://{}:{}'.format('https' if config['use_ssl'] else 'http', config['host'], config['port'])
        if config.get('username') and config.get('password'):
            data = {'username': config['username'],
                    'password': config['password']}
            self._request('post', self.url + '/login', data=data, msg_on_fail='Authentication failed.',
                          verify=config['verify_cert'])
        log.debug('Successfully connected to qBittorrent')
        self.connected = True

    def add_torrent_file(self, file_path, data, verify_cert):
        if not self.connected:
            raise plugin.PluginError('Not connected.')
        multipart_data = {k: (None, v) for k, v in data.items()}
        with open(file_path, 'rb') as f:
            multipart_data['torrents'] = f
            self._request('post', self.url + '/command/upload', msg_on_fail='Failed to add file to qBittorrent',
                          files=multipart_data, verify=verify_cert)
        log.debug('Added torrent file %s to qBittorrent', file_path)

    def add_torrent_url(self, url, data, verify_cert):
        if not self.connected:
            raise plugin.PluginError('Not connected.')
        data['urls'] = url
        multipart_data = {k: (None, v) for k, v in data.items()}
        self._request('post', self.url + '/command/download', msg_on_fail='Failed to add file to qBittorrent',
                      files=multipart_data, verify=verify_cert)
        log.debug('Added url %s to qBittorrent', url)

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('enabled', True)
        config.setdefault('host', 'localhost')
        config.setdefault('port', 8080)
        config.setdefault('use_ssl', False)
        config.setdefault('verify_cert', True)
        config.setdefault('label', '')
        config.setdefault('fail_html', True)
        return config

    def add_entries(self, task, config):
        for entry in task.accepted:
            form_data = {}
            try:
                save_path = entry.render(entry.get('path', config.get('path', '')))
                if save_path:
                    form_data['savepath'] = save_path
            except RenderError as e:
                log.error('Error setting path for %s: %s', entry['title'], e)

            label = entry.get('label', config.get('label'))
            if label:
                form_data['label'] = label  # qBittorrent v3.3.3-
                form_data['category'] = label  # qBittorrent v3.3.4+

            is_magnet = entry['url'].startswith('magnet:')

            if task.manager.options.test:
                log.info('Test mode.')
                log.info('Would add torrent to qBittorrent with:')
                if not is_magnet:
                    log.info('File: %s', entry.get('file'))
                else:
                    log.info('Url: %s', entry.get('url'))
                log.info('Save path: %s', form_data.get('savepath'))
                log.info('Label: %s', form_data.get('label'))
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
                self.add_torrent_file(entry['file'], form_data, config['verify_cert'])
            else:
                self.add_torrent_url(entry['url'], form_data, config['verify_cert'])

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
    plugin.register(OutputQBitTorrent, 'qbittorrent', api_ver=2)
