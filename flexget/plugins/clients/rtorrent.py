import os
import re
import socket
from io import BytesIO
from time import sleep
from urllib.parse import urljoin, urlparse, urlsplit
from xmlrpc import client as xmlrpc_client

import pendulum
from loguru import logger
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.bittorrent import Torrent, is_torrent_file
from flexget.utils.pathscrub import pathscrub
from flexget.utils.template import RenderError

logger = logger.bind(name='rtorrent')


class _Method:
    # some magic to bind an XML-RPC method to an RPC server.
    # supports "nested" methods (e.g. examples.getStateName)

    def __init__(self, send, name):
        self.__send = send
        self.__name = name

    def __getattr__(self, name):
        return _Method(self.__send, f"{self.__name}.{name}")

    def __call__(self, *args):
        return self.__send(self.__name, args)


class HTTPDigestTransport(xmlrpc_client.Transport):
    """Transport that uses requests to support Digest authentication."""

    def __init__(self, scheme, digest_auth, username, password, session, *args, **kwargs):
        self.__scheme = scheme
        self.__session = session
        self.__digest_auth = digest_auth
        self.__username = username
        self.__password = password
        self.verbose = 0
        xmlrpc_client.Transport.__init__(self, *args, **kwargs)  # old style class

    def request(self, host, handler, request_body, verbose=False):
        return self.single_request(host, handler, request_body, verbose)

    def single_request(self, host, handler, request_body, verbose=0):
        url = urljoin(f'{self.__scheme}://{host}', handler)

        auth = self.get_auth()
        response = self.send_request(url, auth, request_body)

        # if status code is 401, it means we used the wrong auth method
        if response.status_code == 401:
            logger.warning(
                '{} auth failed. Retrying with {}. Please change your config.',
                'Digest' if self.__digest_auth else 'Basic',
                'Basic' if self.__digest_auth else 'Digest',
            )
            self.__digest_auth = not self.__digest_auth

            auth = self.get_auth()
            response = self.send_request(url, auth, request_body)

        response.raise_for_status()

        return self.parse_response(response)

    def get_auth(self):
        if self.__digest_auth:
            return HTTPDigestAuth(self.__username, self.__password)
        return HTTPBasicAuth(self.__username, self.__password)

    def send_request(self, url, auth, data):
        return self.__session.post(url, auth=auth, data=data, raise_status=False)

    def parse_response(self, response):
        p, u = self.getparser()

        if self.verbose:
            logger.info('body: {!r}', response)

        p.feed(response.content)
        p.close()

        return u.close()


def encode_netstring(input):
    return str(len(input)).encode() + b':' + input + b','


def encode_header(key, value):
    return key + b'\x00' + value + b'\x00'


class SCGITransport(xmlrpc_client.Transport):
    """Public domain SCGITrannsport implementation from: https://github.com/JohnDoee/autotorrent/blob/develop/autotorrent/scgitransport.py."""

    def __init__(self, *args, **kwargs):
        self.socket_path = kwargs.pop('socket_path', '')
        xmlrpc_client.Transport.__init__(self, *args, **kwargs)

    def single_request(self, host, handler, request_body, verbose=False):
        self.verbose = verbose
        if self.socket_path:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.socket_path)
        else:
            host, port = host.split(':')
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, int(port)))

        request = encode_header(b'CONTENT_LENGTH', str(len(request_body)).encode())
        request += encode_header(b'SCGI', b'1')
        request += encode_header(b'REQUEST_METHOD', b'POST')
        request += encode_header(b'REQUEST_URI', handler.encode())

        request = encode_netstring(request)
        request += request_body

        s.send(request)

        response = b''
        while True:
            r = s.recv(1024)
            if not r:
                break
            response += r

        response_body = BytesIO(b'\r\n\r\n'.join(response.split(b'\r\n\r\n')[1:]))

        return self.parse_response(response_body)


if not hasattr(xmlrpc_client.Transport, 'single_request'):
    SCGITransport.request = SCGITransport.single_request


def create_proxy(url):
    parsed = urlsplit(url)
    if not parsed.scheme:
        path = parsed.path
        return xmlrpc_client.ServerProxy('http://1', transport=SCGITransport(socket_path=path))
    if parsed.scheme == 'scgi':
        url = f'http://{parsed.netloc}'
        return xmlrpc_client.ServerProxy(url, transport=SCGITransport())
    logger.debug('Creating Normal XMLRPC Proxy with url {!r}', url)
    return xmlrpc_client.ServerProxy(url)


class RTorrent:
    """rTorrent API client."""

    default_fields = (
        'hash',
        'name',
        'up_total',
        'down_total',
        'down_rate',
        'is_open',
        'is_active',
        'custom1',
        'custom2',
        'custom3',
        'custom4',
        'custom5',
        'state',
        'complete',
        'bytes_done',
        'down.rate',
        'left_bytes',
        'ratio',
        'base_path',
        'load_date',
        'timestamp_finished',
    )

    required_fields = ('hash', 'name', 'base_path')

    def __init__(self, uri, username=None, password=None, digest_auth=None, session=None):
        """Create new connection to rTorrent.

        :param uri: RTorrent URL. Supports both http(s) and scgi
        :param username: Username for basic auth over http(s)
        :param password: Password for basic auth over http(s)
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.digest_auth = digest_auth
        self._version = None

        parsed_uri = urlparse(uri)

        if self.username and self.password and parsed_uri.scheme not in ['http', 'https']:
            raise OSError('Username and password only supported on http(s)')

        # Determine the proxy server
        if parsed_uri.scheme in ['http', 'https']:
            sp = xmlrpc_client.ServerProxy
        elif parsed_uri.scheme == 'scgi':
            sp = create_proxy
        elif parsed_uri.scheme == '' and parsed_uri.path:
            self.uri = parsed_uri.path
            sp = create_proxy
        else:
            raise OSError(f'Unsupported scheme {parsed_uri.scheme} for uri {self.uri}')

        # Use a special transport if http(s)
        if parsed_uri.scheme in ['http', 'https']:
            self._server = sp(
                self.uri,
                transport=HTTPDigestTransport(
                    parsed_uri.scheme, self.digest_auth, self.username, self.password, session
                ),
            )
        else:
            self._server = sp(self.uri)

    def _clean_fields(self, fields, reverse=False):
        if not fields:
            fields = list(self.default_fields)

        if reverse:
            for field in ['up.total', 'down.total', 'down.rate', 'timestamp.finished']:
                if field in fields:
                    fields[fields.index(field)] = field.replace('.', '_')
            return fields

        for required_field in self.required_fields:
            if required_field not in fields:
                fields.insert(0, required_field)

        for field in ['up_total', 'down_total', 'down_rate', 'timestamp_finished']:
            if field in fields:
                fields[fields.index(field)] = field.replace('_', '.')

        return fields

    def load(self, raw_torrent, fields=None, custom_fields=None, start=False, mkdir=True):
        if fields is None:
            fields = {}

        if custom_fields is None:
            custom_fields = {}

        # First param is empty 'target'
        params = ['', xmlrpc_client.Binary(raw_torrent)]

        # Additional fields to set
        for key, val in fields.items():
            # Values must be escaped if within params
            # TODO: What are the escaping requirements? re.escape works differently on python 3.7+
            params.append(f'd.{key}.set={re.escape(str(val))}')

        # Set custom fields
        for key, val in custom_fields.items():
            # Values must be escaped if within params
            params.append(
                'd.custom.set="{}","{}"'.format(key.replace('"', '\\"'), val.replace('"', '\\"'))
            )

        if mkdir and 'directory' in fields:
            result = self._server.execute.throw('', 'mkdir', '-p', fields['directory'])
            if result != 0:
                raise xmlrpc_client.Error(
                    'Failed creating directory {}'.format(fields['directory'])
                )

        # by default rtorrent won't allow calls over 512kb in size.
        xmlrpc_size = (
            len(xmlrpc_client.dumps(tuple(params), 'raw_start')) + 71680
        )  # Add 70kb for buffer
        if xmlrpc_size > 524288:
            prev_size = self._server.network.xmlrpc.size_limit()
            self._server.network.xmlrpc.size_limit.set('', xmlrpc_size)

        # Call load method and return the response
        result = self._server.load.raw_start(*params) if start else self._server.load.raw(*params)

        if xmlrpc_size > 524288:
            self._server.network.xmlrpc.size_limit.set('', prev_size)

        return result

    def get_directory(self):
        return self._server.get_directory()

    def torrent(self, info_hash, fields=None, custom_fields=None):
        """Get the details of a torrent."""
        if not fields:
            fields = list(self.default_fields)

        if not custom_fields:
            custom_fields = []

        fields = self._clean_fields(fields)

        multi_call = xmlrpc_client.MultiCall(self._server)

        for field in fields:
            method_name = f'd.{field}'
            getattr(multi_call, method_name)(info_hash)

        for custom_field in custom_fields:
            method_name = 'd.custom={}'.format(custom_field.replace('"', '\\"'))
            getattr(multi_call, method_name)(info_hash)

        resp = multi_call()
        # TODO: Maybe we should return a named tuple or a Torrent class?
        return dict(list(zip(self._clean_fields(fields, reverse=True), list(resp))))

    def torrents(self, view='main', fields=None, custom_fields=None):
        if not fields:
            fields = list(self.default_fields)
        fields = self._clean_fields(fields)

        if not custom_fields:
            custom_fields = []

        params = [f'd.{field}=' for field in fields]

        # Set custom fields, and values must be escaped if within params
        params.extend(
            [
                'd.custom={}'.format(custom_field.replace('"', '\\"'))
                for custom_field in custom_fields
            ]
        )

        params.insert(0, view)

        resp = self._server.d.multicall2('', params)

        # Response is formatted as a list of lists, with just the values
        return [
            dict(list(zip(self._clean_fields(fields, reverse=True) + custom_fields, val)))
            for val in resp
        ]

    def update(self, info_hash, fields, custom_fields=None):
        if not fields:
            fields = {}

        if not custom_fields:
            custom_fields = {}

        multi_call = xmlrpc_client.MultiCall(self._server)

        for key, val in fields.items():
            method_name = f'd.{key}.set'
            getattr(multi_call, method_name)(info_hash, val)

        for key, val in custom_fields.items():
            method_name = 'd.custom.set'
            getattr(multi_call, method_name)(info_hash, key, val)

        return multi_call()[0]

    def delete(self, info_hash):
        return self._server.d.erase(info_hash)

    def purge_torrent(self, info_hash):
        torrent = self.torrent(info_hash, fields=['base_path'])
        base_path = torrent['base_path']

        self.stop(info_hash)

        try:
            self._server.execute.throw('', 'rm', '-drf', base_path)
        except xmlrpc_client.Error:
            raise xmlrpc_client.Error(f'Unable to delete data at "{base_path}"')

        return self.delete(info_hash)

    def stop(self, info_hash):
        self._server.d.stop(info_hash)
        return self._server.d.close(info_hash)

    def start(self, info_hash):
        return self._server.d.start(info_hash)

    def move(self, info_hash, dst_path):
        self.stop(info_hash)

        torrent = self.torrent(info_hash, fields=['base_path'])

        try:
            logger.verbose('Creating destination directory `{}`', dst_path)
            self._server.execute.throw('', 'mkdir', '-p', dst_path)
        except xmlrpc_client.Error:
            raise xmlrpc_client.Error(f"unable to create folder {dst_path}")

        self._server.execute.throw('', 'mv', '-u', torrent['base_path'], dst_path)
        self._server.d.set_directory(info_hash, dst_path)
        self.start(info_hash)


class RTorrentPluginBase:
    priority_map = {'high': 3, 'medium': 2, 'low': 1, 'off': 0}

    def _build_options(self, config, entry, entry_first=True):
        options = {}

        for opt_key in (
            'path',
            'message',
            'priority',
            'custom1',
            'custom2',
            'custom3',
            'custom4',
            'custom5',
        ):
            # Values do not merge config with task
            # Task takes priority then config is used
            entry_value = entry.get(opt_key)
            config_value = config.get(opt_key)

            if entry_first:
                if entry_value:
                    options[opt_key] = entry.render(entry_value)
                elif config_value:
                    options[opt_key] = entry.render(config_value)
            elif config_value:
                options[opt_key] = entry.render(config_value)
            elif entry_value:
                options[opt_key] = entry.render(entry_value)

        # Add custom fields on to options
        entry_custom_fields = entry.get('custom_fields', {})
        config_custom_fields = config.get('custom_fields', {})

        if entry_first:
            merged_custom_fields = {**config_custom_fields, **entry_custom_fields}
        else:
            merged_custom_fields = {**entry_custom_fields, **config_custom_fields}

        if merged_custom_fields:
            options['custom_fields'] = {}
            for key, value in merged_custom_fields.items():
                options['custom_fields'][key] = entry.render(value)

        # Convert priority from string to int
        priority = options.get('priority')
        if priority and priority in self.priority_map:
            options['priority'] = self.priority_map[priority]

        # Map Flexget path to directory in rTorrent
        if options.get('path'):
            options['directory'] = options['path']
            del options['path']

        if 'directory' in options:
            options['directory'] = pathscrub(options['directory'])

        return options


class RTorrentOutputPlugin(RTorrentPluginBase):
    schema = {
        'type': 'object',
        'properties': {
            # connection info
            'uri': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'digest_auth': {'type': 'boolean', 'default': False},
            'start': {'type': 'boolean', 'default': True},
            'mkdir': {'type': 'boolean', 'default': True},
            'action': {
                'type': 'string',
                'enum': ['update', 'delete', 'add', 'purge'],
                'default': 'add',
            },
            # properties to set on rtorrent download object
            'message': {'type': 'string'},
            'priority': {'type': 'string'},
            'path': {'type': 'string'},
            'custom1': {'type': 'string'},
            'custom2': {'type': 'string'},
            'custom3': {'type': 'string'},
            'custom4': {'type': 'string'},
            'custom5': {'type': 'string'},
            'fast_resume': {'type': 'boolean', 'default': False},
            'custom_fields': {'type': 'object', 'additionalProperties': {'type': 'string'}},
        },
        'required': ['uri'],
        'additionalProperties': False,
    }

    def _verify_load(self, client, info_hash):
        ex = xmlrpc_client.Error()
        for _ in range(5):
            try:
                return client.torrent(info_hash, fields=['hash'])
            except xmlrpc_client.Error as e:
                ex = e
                sleep(0.5)
        raise ex

    @plugin.priority(120)
    def on_task_download(self, task, config):
        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if config['action'] == 'add' and 'download' not in task.config:
            download = plugin.get('download', self)
            download.get_temp_files(task, handle_magnets=True, fail_html=True)

    @plugin.priority(135)
    def on_task_output(self, task, config):
        client = RTorrent(
            os.path.expanduser(config['uri']),
            username=config.get('username'),
            password=config.get('password'),
            digest_auth=config['digest_auth'],
            session=task.requests,
        )

        try:
            for entry in task.accepted:
                if config['action'] == 'add':
                    if task.options.test:
                        logger.info('Would add {} to rTorrent', entry['url'])
                        continue
                    try:
                        options = self._build_options(config, entry)
                    except RenderError as e:
                        entry.fail(f"failed to render properties {e!s}")
                        continue

                    # fast_resume is not really an rtorrent option so it's not in _build_options
                    fast_resume = entry.get('fast_resume', config['fast_resume'])
                    self.add_entry(
                        client,
                        entry,
                        options,
                        start=config['start'],
                        mkdir=config['mkdir'],
                        fast_resume=fast_resume,
                    )

                info_hash = entry.get('torrent_info_hash')

                if not info_hash:
                    entry.fail('Failed to {} as no info_hash found'.format(config['action']))
                    continue

                if config['action'] == 'delete':
                    if task.options.test:
                        logger.info(
                            'Would delete {} ({}) from rTorrent',
                            entry['title'],
                            entry['torrent_info_hash'],
                        )
                        continue
                    self.delete_entry(client, entry)

                if config['action'] == 'purge':
                    if task.options.test:
                        logger.info(
                            'Would purge {} ({}) from rTorrent',
                            entry['title'],
                            entry['torrent_info_hash'],
                        )
                        continue
                    self.purge_entry(client, entry)

                if config['action'] == 'update':
                    if task.options.test:
                        logger.info(
                            'Would update {} ({}) in rTorrent',
                            entry['title'],
                            entry['torrent_info_hash'],
                        )
                        continue
                    self.update_entry(client, entry, config)

        except OSError as e:
            raise plugin.PluginError(f"Couldn't connect to rTorrent: {e!s}")

    def delete_entry(self, client, entry):
        try:
            client.delete(entry['torrent_info_hash'])
            logger.verbose(
                'Deleted {} ({}) in rtorrent ', entry['title'], entry['torrent_info_hash']
            )
        except xmlrpc_client.Error as e:
            entry.fail(f'Failed to delete: {e!s}')
            return

    def purge_entry(self, client, entry):
        try:
            client.purge_torrent(entry['torrent_info_hash'])
            logger.verbose(
                'Purged {} ({}) in rtorrent ', entry['title'], entry['torrent_info_hash']
            )
        except xmlrpc_client.Error as e:
            entry.fail(f'Failed to purge: {e!s}')
            return

    def update_entry(self, client, entry, config):
        info_hash = entry['torrent_info_hash']

        # First check if it already exists
        try:
            existing = client.torrent(info_hash, fields=['base_path'])
        except xmlrpc_client.Error:
            existing = False

        # Build options but make config values override entry values
        try:
            options = self._build_options(config, entry, entry_first=False)
        except RenderError as e:
            entry.fail(f"failed to render properties {e!s}")
            return

        # Check if changing to another directory which requires a move
        if (
            existing
            and 'directory' in options
            and options['directory'] != existing['base_path']
            and options['directory'] != os.path.dirname(existing['base_path'])
        ):
            try:
                logger.verbose(
                    "Path is changing, moving files from '{}' to '{}'",
                    existing['base_path'],
                    options['directory'],
                )
                client.move(info_hash, options['directory'])
            except xmlrpc_client.Error as e:
                entry.fail(f'Failed moving torrent: {e!s}')
                return

        # Remove directory from update otherwise rTorrent will append the title to the directory path
        if 'directory' in options:
            del options['directory']

        custom_fields = options.pop('custom_fields') if 'custom_fields' in options else {}

        try:
            client.update(info_hash=info_hash, fields=options, custom_fields=custom_fields)
            logger.verbose('Updated {} ({}) in rtorrent ', entry['title'], info_hash)
        except xmlrpc_client.Error as e:
            entry.fail(f'Failed to update: {e!s}')
            return

    def add_entry(self, client, entry, options, start=True, mkdir=False, fast_resume=False):
        if 'torrent_info_hash' not in entry:
            entry.fail('missing torrent_info_hash')
            return

        if entry['url'].startswith('magnet:'):
            torrent_raw = 'd10:magnet-uri{}:{}e'.format(len(entry['url']), entry['url'])
            torrent_raw = torrent_raw.encode('ascii')
        else:
            # Check that file is downloaded
            if 'file' not in entry:
                raise plugin.PluginError('Temporary download file is missing from entry')

            # Verify the temp file exists
            if not os.path.exists(entry['file']):
                raise plugin.PluginError('Temporary download file is missing from disk')

            # Verify valid torrent file
            if not is_torrent_file(entry['file']):
                entry.fail("Downloaded temp file '{}' is not a torrent file".format(entry['file']))
                return

            # Modify the torrent with resume data if needed
            if fast_resume:
                base = options.get('directory')
                if not base:
                    base = client.get_directory()

                piece_size = entry['torrent'].piece_size
                chunks = int((entry['torrent'].size + piece_size - 1) / piece_size)
                files = []

                for f in entry['torrent'].get_filelist():
                    relative_file_path = os.path.join(f['path'], f['name'])
                    if entry['torrent'].is_multi_file:
                        relative_file_path = os.path.join(
                            entry['torrent'].name, relative_file_path
                        )
                    file_path = os.path.join(base, relative_file_path)
                    # TODO: should it simply add the torrent anyway?
                    if not os.path.exists(file_path) and not os.path.isfile(file_path):
                        entry.fail(f'{file_path} does not exist. Cannot add fast resume data.')
                        return
                    # cannot bencode floats, so we need to coerce to int
                    mtime = int(os.path.getmtime(file_path))
                    # priority 0 should be "don't download"
                    files.append({'priority': 0, 'mtime': mtime})

                entry['torrent'].set_libtorrent_resume(chunks, files)
                # Since we modified the torrent, we need to write it to entry['file'] again
                with open(entry['file'], 'wb+') as f:
                    f.write(entry['torrent'].encode())
            try:
                with open(entry['file'], 'rb') as f:
                    torrent_raw = f.read()
            except OSError as e:
                entry.fail(f'Failed to add to rTorrent {e!s}')
                return

            try:
                Torrent(torrent_raw)
            except SyntaxError as e:
                entry.fail(f'Strange, unable to decode torrent, raise a BUG: {e!s}')
                return

        # First check if it already exists
        try:
            if client.torrent(entry['torrent_info_hash']):
                logger.warning("Torrent {} already exists, won't add", entry['title'])
                return
        except xmlrpc_client.Error:
            # No existing found
            pass

        # Setup options and custom fields
        custom_fields = options.pop('custom_fields', {})

        try:
            resp = client.load(
                torrent_raw, fields=options, custom_fields=custom_fields, start=start, mkdir=mkdir
            )
            if resp != 0:
                entry.fail(f'Failed to add to rTorrent invalid return value {resp}')
        except xmlrpc_client.Error as e:
            logger.exception('Found an error')
            entry.fail(f'Failed to add to rTorrent {e!s}')
            return

        # Verify the torrent loaded
        try:
            self._verify_load(client, entry['torrent_info_hash'])
            logger.info('{} added to rtorrent', entry['title'])
        except xmlrpc_client.Error as e:
            logger.warning('Failed to verify torrent {} loaded: {}', entry['title'], str(e))

    def on_task_learn(self, task, config):
        """Make sure all temp files are cleaned up when entries are learned."""
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get('download', self)
            download.cleanup_temp_files(task)

    on_task_abort = on_task_learn


class RTorrentInputPlugin(RTorrentPluginBase):
    schema = {
        'type': 'object',
        'properties': {
            'uri': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'digest_auth': {'type': 'boolean', 'default': False},
            'view': {'type': 'string', 'default': 'main'},
            'fields': one_or_more({'type': 'string', 'enum': list(RTorrent.default_fields)}),
            'custom_fields': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['uri'],
        'additionalProperties': False,
    }

    def on_task_input(self, task, config):
        client = RTorrent(
            os.path.expanduser(config['uri']),
            username=config.get('username'),
            password=config.get('password'),
            digest_auth=config['digest_auth'],
            session=task.requests,
        )

        fields = config.get('fields')
        custom_fields = config.get('custom_fields')

        try:
            torrents = client.torrents(config['view'], fields=fields, custom_fields=custom_fields)
        except (OSError, xmlrpc_client.Error) as e:
            task.abort('Could not get torrents ({}): {}'.format(config['view'], e))
            return None

        entries = []

        for torrent in torrents:
            entry = Entry(
                title=torrent['name'],
                url='{}/{}'.format(os.path.expanduser(config['uri']), torrent['hash']),
                path=torrent['base_path'],
                torrent_info_hash=torrent['hash'],
            )

            for attr, value in torrent.items():
                entry[attr] = value

            if 'timestamp_finished' in entry:
                entry['timestamp_finished'] = pendulum.from_timestamp(entry['timestamp_finished'])

            entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(RTorrentOutputPlugin, 'rtorrent', api_ver=2)
    plugin.register(RTorrentInputPlugin, 'from_rtorrent', api_ver=2)
