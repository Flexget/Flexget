import os

from loguru import logger
from requests import Session
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError

logger = logger.bind(name='qbittorrent')


class OutputQBitTorrent:
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
        maxupspeed: <torrent upload speed limit> (default: 0)
        maxdownspeed: <torrent download speed limit> (default: 0)
        add_paused: <ADD_PAUSED> (default: False)
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
                    'maxupspeed': {'type': 'integer'},
                    'maxdownspeed': {'type': 'integer'},
                    'fail_html': {'type': 'boolean'},
                    'add_paused': {'type': 'boolean'},
                    'skip_check': {'type': 'boolean'},
                },
                'additionalProperties': False,
            },
        ]
    }

    def __init__(self):
        super().__init__()
        self.session = Session()
        self.api_url_login = None
        self.api_url_upload = None
        self.api_url_download = None
        self.url = None
        self.connected = False

    def _request(self, method, url, msg_on_fail=None, **kwargs):
        try:
            response = self.session.request(method, url, **kwargs)
            if response.text == "Ok.":
                return response
            msg = msg_on_fail if msg_on_fail else f'Failure. URL: {url}, data: {kwargs}'
        except RequestException as e:
            msg = str(e)
        raise plugin.PluginError(f'Error when trying to send request to qBittorrent: {msg}')

    def check_api_version(self, msg_on_fail, verify=True):
        try:
            url = self.url + "/api/v2/app/webapiVersion"
            response = self.session.request('get', url, verify=verify)
            if response.status_code != 404:
                self.api_url_login = '/api/v2/auth/login'
                self.api_url_upload = '/api/v2/torrents/add'
                self.api_url_download = '/api/v2/torrents/add'
                return response

            url = self.url + "/version/api"
            response = self.session.request('get', url, verify=verify)
            if response.status_code != 404:
                self.api_url_login = '/login'
                self.api_url_upload = '/command/upload'
                self.api_url_download = '/command/download'
                return response

            msg = 'Failure. URL: {}'.format(url) if not msg_on_fail else msg_on_fail
        except RequestException as e:
            msg = str(e)
        raise plugin.PluginError(
            'Error when trying to send request to qBittorrent: {}'.format(msg)
        )

    def connect(self, config):
        """
        Connect to qBittorrent Web UI. Username and password not necessary
        if 'Bypass authentication for localhost' is checked and host is
        'localhost'.
        """
        self.url = '{}://{}:{}'.format(
            'https' if config['use_ssl'] else 'http', config['host'], config['port']
        )
        self.check_api_version('Check API version failed.', verify=config['verify_cert'])
        if config.get('username') and config.get('password'):
            data = {'username': config['username'], 'password': config['password']}
            self._request(
                'post',
                self.url + self.api_url_login,
                data=data,
                msg_on_fail='Authentication failed.',
                verify=config['verify_cert'],
            )
        logger.debug('Successfully connected to qBittorrent')
        self.connected = True

    def add_torrent_file(self, file_path, data, verify_cert):
        if not self.connected:
            raise plugin.PluginError('Not connected.')
        multipart_data = {k: (None, v) for k, v in data.items()}
        with open(file_path, 'rb') as f:
            multipart_data['torrents'] = f
            self._request(
                'post',
                self.url + self.api_url_upload,
                msg_on_fail='Failed to add file to qBittorrent',
                files=multipart_data,
                verify=verify_cert,
            )
        logger.debug('Added torrent file {} to qBittorrent', file_path)

    def add_torrent_url(self, url, data, verify_cert):
        if not self.connected:
            raise plugin.PluginError('Not connected.')
        data['urls'] = url
        multipart_data = {k: (None, v) for k, v in data.items()}
        self._request(
            'post',
            self.url + self.api_url_download,
            msg_on_fail='Failed to add file to qBittorrent',
            files=multipart_data,
            verify=verify_cert,
        )
        logger.debug('Added url {} to qBittorrent', url)

    @staticmethod
    def prepare_config(config):
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('enabled', True)
        config.setdefault('host', 'localhost')
        config.setdefault('port', 8080)
        config.setdefault('use_ssl', False)
        config.setdefault('verify_cert', True)
        config.setdefault('label', '')
        config.setdefault('maxupspeed', 0)
        config.setdefault('maxdownspeed', 0)
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
                logger.error('Error setting path for {}: {}', entry['title'], e)

            label = entry.render(entry.get('label', config.get('label', '')))
            if label:
                form_data['label'] = label  # qBittorrent v3.3.3-
                form_data['category'] = label  # qBittorrent v3.3.4+

            add_paused = entry.get('add_paused', config.get('add_paused'))
            if add_paused:
                form_data['paused'] = 'true'

            skip_check = entry.get('skip_check', config.get('skip_check'))
            if skip_check:
                form_data['skip_checking'] = 'true'

            maxupspeed = entry.get('maxupspeed', config.get('maxupspeed'))
            if maxupspeed:
                form_data['upLimit'] = maxupspeed * 1024

            maxdownspeed = entry.get('maxdownspeed', config.get('maxdownspeed'))
            if maxdownspeed:
                form_data['dlLimit'] = maxdownspeed * 1024

            is_magnet = entry['url'].startswith('magnet:')

            if task.manager.options.test:
                logger.info('Test mode.')
                logger.info('Would add torrent to qBittorrent with:')
                if not is_magnet:
                    logger.info('File: {}', entry.get('file'))
                else:
                    logger.info('Url: {}', entry.get('url'))
                logger.info('Save path: {}', form_data.get('savepath'))
                logger.info('Label: {}', form_data.get('label'))
                logger.info('Paused: {}', form_data.get('paused', 'false'))
                logger.info('Skip Hash Check: {}', form_data.get('skip_checking', 'false'))
                if maxupspeed:
                    logger.info('Upload Speed Limit: {}', form_data.get('upLimit'))
                if maxdownspeed:
                    logger.info('Download Speed Limit: {}', form_data.get('dlLimit'))
                continue

            if not is_magnet:
                if 'file' not in entry:
                    entry.fail('File missing?')
                    continue
                if not os.path.exists(entry['file']):
                    tmp_path = os.path.join(task.manager.config_base, 'temp')
                    logger.debug('entry: {}', entry)
                    logger.debug('temp: {}', ', '.join(os.listdir(tmp_path)))
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
            download = plugin.get('download', self)
            download.get_temp_files(task, handle_magnets=True, fail_html=config['fail_html'])

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
