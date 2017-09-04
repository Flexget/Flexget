from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.xmlrpc import client as xmlrpc_client
from future.moves.urllib.parse import urlparse, urljoin
from future.utils import native_str

import logging
import os
import socket
import re
from time import sleep

from flexget.utils.template import RenderError
from flexget.utils.pathscrub import pathscrub
from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.config_schema import one_or_more
from flexget.utils.bittorrent import Torrent, is_torrent_file

from requests.auth import HTTPDigestAuth, HTTPBasicAuth

log = logging.getLogger('rtorrent')


class _Method(object):
    # some magic to bind an XML-RPC method to an RPC server.
    # supports "nested" methods (e.g. examples.getStateName)

    def __init__(self, send, name):
        self.__send = send
        self.__name = name

    def __getattr__(self, name):
        return _Method(self.__send, "%s.%s" % (self.__name, name))

    def __call__(self, *args):
        return self.__send(self.__name, args)


class HTTPDigestTransport(xmlrpc_client.Transport):
    """
    Transport that uses requests to support Digest authentication.
    """

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
        url = urljoin('{0}://{1}'.format(self.__scheme, host), handler)

        auth = self.get_auth()
        response = self.send_request(url, auth, request_body)

        # if status code is 401, it means we used the wrong auth method
        if response.status_code == 401:
            log.warning('%s auth failed. Retrying with %s. Please change your config.',
                        'Digest' if self.__digest_auth else 'Basic',
                        'Basic' if self.__digest_auth else 'Digest')
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
            log.info('body: %s', repr(response))

        p.feed(response.content)
        p.close()

        return u.close()


class SCGITransport(xmlrpc_client.Transport):
    """ Used to override the default xmlrpclib transport to support SCGI """

    def __init__(self, *args, **kwargs):
        self.verbose = 0
        xmlrpc_client.Transport.__init__(self, *args, **kwargs)

    def request(self, host, handler, request_body, verbose=False):
        return self.single_request(host, handler, request_body, verbose)

    def single_request(self, host, handler, request_body, verbose=0):
        # Add SCGI headers to the request.
        headers = [('CONTENT_LENGTH', native_str(len(request_body))), ('SCGI', '1')]
        header = '\x00'.join(['%s\x00%s' % (key, value) for key, value in headers]) + '\x00'
        header = '%d:%s' % (len(header), header)
        request_body = '%s,%s' % (header, request_body)

        sock = None

        try:
            if host:
                parsed_host = urlparse(host)
                host = parsed_host.hostname
                port = parsed_host.port

                addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
                sock = socket.socket(*addr_info[0][:3])
                sock.connect(addr_info[0][4])
            else:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(handler)

            self.verbose = verbose

            sock.sendall(request_body.encode())

            return self.parse_response(sock.makefile())
        finally:
            if sock:
                sock.close()

    def parse_response(self, response):
        p, u = self.getparser()

        response_body = ''

        while True:
            data = response.read(1024)
            if not data:
                break
            response_body += data

        if self.verbose:
            log.info('body: %s', repr(response_body))

        # Remove SCGI headers from the response.
        _, response_body = re.split(r'\n\s*?\n', response_body, maxsplit=1)
        p.feed(response_body)
        p.close()

        return u.close()


class SCGIServerProxy(object):
    """ Enable connection to SCGI proxy """

    def __init__(self, uri, transport=None, encoding=None,
                 verbose=False, allow_none=False, use_datetime=False):
        parsed_url = urlparse(uri)
        self.__host = uri if parsed_url.scheme else None
        self.__handler = parsed_url.path
        if not self.__handler:
            self.__handler = '/'

        if not transport:
            transport = SCGITransport(use_datetime=use_datetime)
        self.__transport = transport
        self.__encoding = encoding or 'utf-8'
        self.__verbose = verbose
        self.__allow_none = allow_none

    def __close(self):
        self.__transport.close()

    def __request(self, method_name, params):
        # call a method on the remote server

        request = xmlrpc_client.dumps(params, method_name, encoding=self.__encoding,
                                      allow_none=self.__allow_none).encode(self.__encoding)

        response = self.__transport.request(
            self.__host,
            self.__handler,
            request.decode('utf-8'),
            verbose=self.__verbose
        )

        if len(response) == 1:
            response = response[0]

        return response

    def __repr__(self):
        return (
            "<ServerProxy for %s%s>" %
            (self.__host, self.__handler)
        )

    __str__ = __repr__

    def __getattr__(self, name):
        # magic method dispatcher
        return _Method(self.__request, name)

    # note: to call a remote object with an non-standard name, use
    # result getattr(server, "strange-python-name")(args)

    def __call__(self, attr):
        """A workaround to get special attributes on the ServerProxy
           without interfering with the magic __getattr__
        """
        if attr == "close":
            return self.__close
        elif attr == "transport":
            return self.__transport
        raise AttributeError("Attribute %r not found" % (attr,))


class RTorrent(object):
    """ rTorrent API client """

    default_fields = (
        'hash',
        'name',
        'up_total', 'down_total', 'down_rate',
        'is_open', 'is_active',
        'custom1', 'custom2', 'custom3', 'custom4', 'custom5',
        'state', 'complete',
        'bytes_done', 'down.rate', 'left_bytes',
        'ratio',
        'base_path', 'load_date'
    )

    required_fields = (
        'hash',
        'name',
        'base_path'
    )

    def __init__(self, uri, username=None, password=None, digest_auth=None, session=None):
        """
        New connection to rTorrent

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
            raise IOError('Username and password only supported on http(s)')

        # Determine the proxy server
        if parsed_uri.scheme in ['http', 'https']:
            sp = xmlrpc_client.ServerProxy
        elif parsed_uri.scheme == 'scgi':
            sp = SCGIServerProxy
        elif parsed_uri.scheme == '' and parsed_uri.path:
            self.uri = parsed_uri.path
            sp = SCGIServerProxy
        else:
            raise IOError('Unsupported scheme %s for uri %s' % (parsed_uri.scheme, self.uri))

        # Use a special transport if http(s)
        if parsed_uri.scheme in ['http', 'https']:
            self._server = sp(self.uri, transport=HTTPDigestTransport(parsed_uri.scheme, self.digest_auth,
                                                                      self.username, self.password, session))
        else:
            self._server = sp(self.uri)

    def _clean_fields(self, fields, reverse=False):
        if not fields:
            fields = list(self.default_fields)

        if reverse:
            for field in ['up.total', 'down.total', 'down.rate']:
                if field in fields:
                    fields[fields.index(field)] = native_str(field.replace('.', '_'))
            return fields

        for required_field in self.required_fields:
            if required_field not in fields:
                fields.insert(0, required_field)

        for field in ['up_total', 'down_total', 'down_rate']:
            if field in fields:
                fields[fields.index(field)] = native_str(field.replace('_', '.'))

        return fields

    @property
    def version(self):
        return [int(v) for v in self._server.system.client_version().split('.')]

    def load(self, raw_torrent, fields=None, start=False, mkdir=True):

        if fields is None:
            fields = {}
        # First param is empty 'target'
        params = ['', xmlrpc_client.Binary(raw_torrent)]

        # Additional fields to set
        for key, val in fields.items():
            # Values must be escaped if within params
            params.append('d.%s.set=%s' % (key, re.escape(native_str(val))))

        if mkdir and 'directory' in fields:
            result = self._server.execute.throw('', 'mkdir', '-p', fields['directory'])
            if result != 0:
                raise xmlrpc_client.Error('Failed creating directory %s' % fields['directory'])

        # by default rtorrent won't allow calls over 512kb in size.
        xmlrpc_size = len(xmlrpc_client.dumps(tuple(params), 'raw_start')) + 71680  # Add 70kb for buffer
        if xmlrpc_size > 524288:
            prev_size = self._server.network.xmlrpc.size_limit()
            self._server.network.xmlrpc.size_limit.set('', xmlrpc_size)

        # Call load method and return the response
        if start:
            result = self._server.load.raw_start(*params)
        else:
            result = self._server.load.raw(*params)

        if xmlrpc_size > 524288:
            self._server.network.xmlrpc.size_limit.set('', prev_size)

        return result

    def torrent(self, info_hash, fields=None):
        """ Get the details of a torrent """
        info_hash = native_str(info_hash)
        if not fields:
            fields = list(self.default_fields)

        fields = self._clean_fields(fields)

        multi_call = xmlrpc_client.MultiCall(self._server)

        for field in fields:
            method_name = 'd.%s' % field
            getattr(multi_call, method_name)(info_hash)

        resp = multi_call()
        # TODO: Maybe we should return a named tuple or a Torrent class?
        return dict(list(zip(self._clean_fields(fields, reverse=True), [val for val in resp])))

    def torrents(self, view='main', fields=None):
        if not fields:
            fields = list(self.default_fields)
        fields = self._clean_fields(fields)

        params = ['d.%s=' % field for field in fields]
        params.insert(0, view)

        resp = self._server.d.multicall(params)

        # Response is formatted as a list of lists, with just the values
        return [dict(list(zip(self._clean_fields(fields, reverse=True), val))) for val in resp]

    def update(self, info_hash, fields):
        multi_call = xmlrpc_client.MultiCall(self._server)

        for key, val in fields.items():
            method_name = 'd.%s.set' % key
            getattr(multi_call, method_name)(native_str(info_hash), native_str(val))

        return multi_call()[0]

    def delete(self, info_hash):
        return self._server.d.erase(native_str(info_hash))

    def stop(self, info_hash):
        self._server.d.stop(info_hash)
        return self._server.d.close(native_str(info_hash))

    def start(self, info_hash):
        return self._server.d.start(native_str(info_hash))

    def move(self, info_hash, dst_path):
        info_hash = native_str(info_hash)
        self.stop(info_hash)

        torrent = self.torrent(info_hash, fields=['base_path'])

        try:
            log.verbose('Creating destination directory `%s`' % dst_path)
            self._server.execute.throw('', 'mkdir', '-p', dst_path)
        except xmlrpc_client.Error:
            raise xmlrpc_client.Error("unable to create folder %s" % dst_path)

        self._server.execute.throw('', 'mv', '-u', torrent['base_path'], dst_path)
        self._server.d.set_directory(info_hash, dst_path)
        self.start(info_hash)


class RTorrentPluginBase(object):
    priority_map = {
        'high': 3,
        'medium': 2,
        'low': 1,
        'off': 0,
    }

    def _build_options(self, config, entry, entry_first=True):
        options = {}

        for opt_key in ('path', 'message', 'priority',
                        'custom1', 'custom2', 'custom3', 'custom4', 'custom5'):
            # Values do not merge config with task
            # Task takes priority then config is used
            entry_value = entry.get(opt_key)
            config_value = config.get(opt_key)

            if entry_first:
                if entry_value:
                    options[opt_key] = entry.render(entry_value)
                elif config_value:
                    options[opt_key] = entry.render(config_value)
            else:
                if config_value:
                    options[opt_key] = entry.render(config_value)
                elif entry_value:
                    options[opt_key] = entry.render(entry_value)

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

    def on_task_start(self, task, config):
        try:
            client = RTorrent(os.path.expanduser(config['uri']),
                              username=config.get('username'),
                              password=config.get('password'),
                              digest_auth=config['digest_auth'],
                              session=task.requests)
            if client.version < [0, 9, 2]:
                log.error('rtorrent version >=0.9.2 required, found {0}'.format('.'.join(map(str, client.version))))
                task.abort('rtorrent version >=0.9.2 required, found {0}'.format('.'.join(map(str, client.version))))
        except (IOError, xmlrpc_client.Error) as e:
            raise plugin.PluginError("Couldn't connect to rTorrent: %s" % str(e))


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
            'action': {'type': 'string', 'emun': ['update', 'delete', 'add'], 'default': 'add'},
            # properties to set on rtorrent download object
            'message': {'type': 'string'},
            'priority': {'type': 'string'},
            'path': {'type': 'string'},
            'custom1': {'type': 'string'},
            'custom2': {'type': 'string'},
            'custom3': {'type': 'string'},
            'custom4': {'type': 'string'},
            'custom5': {'type': 'string'},
        },
        'required': ['uri'],
        'additionalProperties': False,
    }

    def _verify_load(self, client, info_hash):
        ex = IOError()
        for _ in range(0, 5):
            try:
                return client.torrent(info_hash, fields=['hash'])
            except (IOError, xmlrpc_client.Error) as e:
                ex = e
                sleep(0.5)
        raise ex

    @plugin.priority(120)
    def on_task_download(self, task, config):
        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if config['action'] == 'add' and 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

    @plugin.priority(135)
    def on_task_output(self, task, config):
        client = RTorrent(os.path.expanduser(config['uri']),
                          username=config.get('username'),
                          password=config.get('password'),
                          digest_auth=config['digest_auth'],
                          session=task.requests)

        for entry in task.accepted:

            if config['action'] == 'add':
                if task.options.test:
                    log.info('Would add %s to rTorrent', entry['url'])
                    continue
                try:
                    options = self._build_options(config, entry)
                except RenderError as e:
                    entry.fail("failed to render properties %s" % str(e))
                    continue

                self.add_entry(client, entry, options, start=config['start'], mkdir=config['mkdir'])

            info_hash = entry.get('torrent_info_hash')

            if not info_hash:
                entry.fail('Failed to %s as no info_hash found' % config['action'])
                continue

            if config['action'] == 'delete':
                if task.options.test:
                    log.info('Would delete %s (%s) from rTorrent', entry['title'], entry['torrent_info_hash'])
                    continue
                self.delete_entry(client, entry)

            if config['action'] == 'update':
                if task.options.test:
                    log.info('Would update %s (%s) in rTorrent', entry['title'], entry['torrent_info_hash'])
                    continue
                self.update_entry(client, entry, config)

    def delete_entry(self, client, entry):
        try:
            client.delete(entry['torrent_info_hash'])
            log.verbose('Deleted %s (%s) in rtorrent ' % (entry['title'], entry['torrent_info_hash']))
        except (IOError, xmlrpc_client.Error) as e:
            entry.fail('Failed to delete: %s' % str(e))
            return

    def update_entry(self, client, entry, config):
        info_hash = entry['torrent_info_hash']

        # First check if it already exists
        try:
            existing = client.torrent(info_hash, fields=['base_path'])
        except IOError as e:
            entry.fail("Error updating torrent %s" % str(e))
            return
        except xmlrpc_client.Error as e:
            existing = False

        # Build options but make config values override entry values
        try:
            options = self._build_options(config, entry, entry_first=False)
        except RenderError as e:
            entry.fail("failed to render properties %s" % str(e))
            return

        if existing and 'directory' in options:
            # Check if changing to another directory which requires a move
            if options['directory'] != existing['base_path'] \
                    and options['directory'] != os.path.dirname(existing['base_path']):
                try:
                    log.verbose("Path is changing, moving files from '%s' to '%s'"
                                % (existing['base_path'], options['directory']))
                    client.move(info_hash, options['directory'])
                except (IOError, xmlrpc_client.Error) as e:
                    entry.fail('Failed moving torrent: %s' % str(e))
                    return

        # Remove directory from update otherwise rTorrent will append the title to the directory path
        if 'directory' in options:
            del options['directory']

        try:
            client.update(info_hash, options)
            log.verbose('Updated %s (%s) in rtorrent ' % (entry['title'], info_hash))
        except (IOError, xmlrpc_client.Error) as e:
            entry.fail('Failed to update: %s' % str(e))
            return

    def add_entry(self, client, entry, options, start=True, mkdir=False):

        if 'torrent_info_hash' not in entry:
            entry.fail('missing torrent_info_hash')
            return

        if entry['url'].startswith('magnet:'):
            torrent_raw = 'd10:magnet-uri%d:%se' % (len(entry['url']), entry['url'])
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
                entry.fail("Downloaded temp file '%s' is not a torrent file" % entry['file'])
                return

            try:
                with open(entry['file'], 'rb') as f:
                    torrent_raw = f.read()
            except IOError as e:
                entry.fail('Failed to add to rTorrent %s' % str(e))
                return

            try:
                Torrent(torrent_raw)
            except SyntaxError as e:
                entry.fail('Strange, unable to decode torrent, raise a BUG: %s' % str(e))
                return

        # First check if it already exists
        try:
            if client.torrent(entry['torrent_info_hash']):
                log.warning("Torrent %s already exists, won't add" % entry['title'])
                return
        except IOError as e:
            entry.fail("Error checking if torrent already exists %s" % str(e))
        except xmlrpc_client.Error:
            # No existing found
            pass

        try:
            resp = client.load(torrent_raw, fields=options, start=start, mkdir=mkdir)
            if resp != 0:
                entry.fail('Failed to add to rTorrent invalid return value %s' % resp)
        except (IOError, xmlrpc_client.Error) as e:
            log.exception(e)
            entry.fail('Failed to add to rTorrent %s' % str(e))
            return

        # Verify the torrent loaded
        try:
            self._verify_load(client, entry['torrent_info_hash'])
            log.info('%s added to rtorrent' % entry['title'])
        except (IOError, xmlrpc_client.Error) as e:
            entry.fail('Failed to verify torrent loaded: %s' % str(e))

    def on_task_learn(self, task, config):
        """ Make sure all temp files are cleaned up when entries are learned """
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.cleanup_temp_files(task)

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
        },
        'required': ['uri'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        client = RTorrent(os.path.expanduser(config['uri']),
                          username=config.get('username'),
                          password=config.get('password'),
                          digest_auth=config['digest_auth'],
                          session=task.requests)

        fields = config.get('fields')

        try:
            torrents = client.torrents(config['view'], fields=fields)
        except (IOError, xmlrpc_client.Error) as e:
            task.abort('Could not get torrents (%s): %s' % (config['view'], e))
            return

        entries = []

        for torrent in torrents:
            entry = Entry(
                title=torrent['name'],
                url='%s/%s' % (os.path.expanduser(config['uri']),
                               torrent['hash']),
                path=torrent['base_path'],
                torrent_info_hash=torrent['hash'],
            )

            for attr, value in torrent.items():
                entry[attr] = value

            entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(RTorrentOutputPlugin, 'rtorrent', api_ver=2)
    plugin.register(RTorrentInputPlugin, 'from_rtorrent', api_ver=2)
