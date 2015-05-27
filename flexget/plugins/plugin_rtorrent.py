import logging

import sys
import os
import socket
import re
import xmlrpclib
from time import sleep
from urlparse import urlparse

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.config_schema import one_or_more
from flexget.utils.bittorrent import Torrent, is_torrent_file


log = logging.getLogger('rtorrent')


class SCGITransport(xmlrpclib.Transport):
    """ Used to override the default xmlrpclib transport to support SCGI """

    def request(self, host, handler, request_body, verbose=False):
        return self.single_request(host, handler, request_body, verbose)

    def single_request(self, host, handler, request_body, verbose=0):
        # Add SCGI headers to the request.
        headers = [('CONTENT_LENGTH', str(len(request_body))), ('SCGI', '1')]
        header = '\x00'.join(['%s\x00%s' % (key, value) for key, value in headers]) + '\x00'
        header = '%d:%s' % (len(header), header)
        request_body = '%s,%s' % (header, request_body)

        sock = None

        try:
            if host:
                parsed_host = urlparse(host)
                host = parsed_host.hostname
                port = parsed_host.port

                addr_info = socket.getaddrinfo(host, int(port), socket.AF_INET, socket.SOCK_STREAM)
                sock = socket.socket(*addr_info[0][:3])
                sock.connect(addr_info[0][4])
            else:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(handler)

            self.verbose = verbose

            if sys.version_info[0] > 2:
                sock.send(bytes(request_body, 'utf-8'))
            else:
                sock.send(request_body)
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
            log.info('body:', repr(response_body))

        # Remove SCGI headers from the response.
        response_header, response_body = re.split(r'\n\s*?\n', response_body, maxsplit=1)
        p.feed(response_body)
        p.close()

        return u.close()


class SCGIServerProxy(xmlrpclib.ServerProxy):
    """ Enable connection to SCGI proxy """

    def __init__(self, uri, transport=None, encoding=None, verbose=False, allow_none=False, use_datetime=False):
        parsed_uri = urlparse(uri)
        self.uri = uri
        self.__host = uri
        self.__handler = parsed_uri.path
        if not self.__handler:
            self.__handler = '/'

        if not transport:
            transport = SCGITransport(use_datetime=use_datetime)
        self.__transport = transport
        self.__encoding = encoding
        self.__verbose = verbose
        self.__allow_none = allow_none

    def __close(self):
        self.__transport.close()

    def __request(self, method_name, params):
        # call a method on the remote server
        request = xmlrpclib.dumps(params, method_name, encoding=self.__encoding, allow_none=self.__allow_none)
        response = self.__transport.request(self.uri, self.__handler, request, verbose=self.__verbose)

        if len(response) == 1:
            response = response[0]

        return response

    def __repr__(self):
        return '<SCGIServerProxy for %s%s>' % (self.__host, self.__handler)

    def __getattr__(self, name):
        # magic method dispatcher
        return xmlrpclib._Method(self.__request, name)

    # note: to call a remote object with an non-standard name, use
    # result getattr(server, "strange-python-name")(args)
    def __call__(self, attr):
        """
        A workaround to get special attributes on the ServerProxy
        without interfering with the magic __getattr__
        """
        if attr == 'close':
            return self.__close
        elif attr == 'transport':
            return self.__transport
        raise AttributeError('Attribute %r not found' % (attr,))


class RTorrent(object):
    """ rTorrent API client """

    default_fields = [
        'hash',
        'name',
        'up_total', 'down_total', 'down_rate',
        'is_open', 'is_active',
        'custom1', 'custom2', 'custom3', 'custom4', 'custom5',
        'state', 'complete',
        'bytes_done', 'down.rate', 'left_bytes',
        'ratio',
        'directory_base'
    ]

    required_fields = [
        'hash',
        'name',
        'directory_base'
    ]

    def __init__(self, uri, username=None, password=None):
        """
        New connection to rTorrent

        :param uri: RTorrent URL. Supports both http(s) and scgi
        :param username: Username for basic auth over http(s)
        :param password: Password for basic auth over http(s)
        """
        self.uri = uri
        self.username = username
        self.password = password
        self._version = None

        parsed_uri = urlparse(uri)

        # Reformat uri with username and password for HTTP(s) Auth
        if self.username and self.password:
            if parsed_uri.scheme not in ['http', 'https']:
                raise IOError('Username and password only supported on http(s)')

            data = {
                'scheme': parsed_uri.scheme,
                'hostname': parsed_uri.hostname,
                'port': parsed_uri.port,
                'path': parsed_uri.path,
                'query': parsed_uri.query,
                'username': self.username,
                'password': self.password,
            }
            self.uri = '%(scheme)s://%(username)s:%(password)s@%(hostname)s%(path)s%(query)s' % data

        # Determine the proxy server
        if parsed_uri.scheme in ['http', 'https']:
            sp = xmlrpclib.ServerProxy
        elif parsed_uri.scheme == 'scgi':
            sp = SCGIServerProxy
        else:
            raise IOError('Unsupported scheme %s for uri %s' % (parsed_uri.scheme, self.uri))

        self._server = sp(self.uri)

    def _clean_fields(self, fields, reverse=False):
        if reverse:
            for field in ['up.total', 'down.total', 'down.rate']:
                if field in fields:
                    fields[fields.index(field)] = field.replace('.', '_')
            return fields

        if not fields:
            return self.default_fields
        for required_field in self.required_fields:
            if required_field not in fields:
                fields.insert(0, required_field)

        for field in ['up_total', 'down_total', 'down_rate']:
            if field in fields:
                fields[fields.index(field)] = field.replace('_', '.')

        return fields

    @property
    def version(self):
        return [int(v) for v in self._server.system.client_version().split('.')]

    def load(self, raw_torrent, fields={}, start=False, mkdir=True):

        # First param is empty 'target'
        params = ['', xmlrpclib.Binary(raw_torrent)]

        # Additional fields to set
        for key, val in fields.iteritems():
            params.append('d.{0}.set={1}'.format(key, val))

        if mkdir and 'directory' in fields:
            result = self._server.execute.throw('', 'mkdir', '-p', fields['directory'])
            if result != 0:
                raise xmlrpclib.Error('Failed creating directory %s' % fields['directory'])

        # Call load method and return the response
        if start:
            return self._server.load.raw_start(*params)
        else:
            return self._server.load.raw(*params)

    def torrent(self, info_hash, fields=default_fields):
        """ Get the details of a torrent """
        fields = self._clean_fields(fields)

        multi_call = xmlrpclib.MultiCall(self._server)

        for field in fields:
            method_name = 'd.%s' % field
            getattr(multi_call, method_name)(info_hash)

        resp = multi_call()
        return dict(zip(self._clean_fields(fields, reverse=True), [val for val in resp]))

    def torrents(self, view='main', fields=default_fields):
        fields = self._clean_fields(fields)

        params = ['d.%s=' % field for field in fields]
        params.insert(0, view)

        resp = self._server.d.multicall(params)

        # Response is formatted as a list of lists, with just the values
        return [dict(zip(self._clean_fields(fields, reverse=True), val)) for val in resp]

    def update(self, info_hash, fields):
        multi_call = xmlrpclib.MultiCall(self._server)

        for key, val in fields.iteritems():
            method_name = 'd.set_{0}'.format(key)
            getattr(multi_call, method_name)(info_hash, val)

        return multi_call()[0]

    def delete(self, info_hash):
        return self._server.d.erase(info_hash)


class RTorrentPluginBase(object):

    priority_map = {
        'high': 3,
        'medium': 2,
        'low': 1,
        'off': 0,
    }

    def _build_options(self, config, entry):
        options = {}

        for opt_key in ('path', 'message', 'priority',
                        'custom1', 'custom2', 'custom3', 'custom4', 'custom5'):
            # Values do not merge config with task
            # Task takes priority then config is used
            if opt_key in entry:
                options[opt_key] = entry[opt_key]
            elif opt_key in config:
                options[opt_key] = config[opt_key]

        # Convert priority from string to int
        priority = options.get('priority')
        if priority and priority in self.priority_map:
            options['priority'] = self.priority_map[priority]

        # Map Flexget path to directory in rTorrent
        if options.get('path'):
            options['directory'] = options['path']
            del options['path']

        return options

    def on_task_start(self, task, config):
        try:
            client = RTorrent(config['uri'], username=config.get('username'), password=config.get('password'))
            if client.version < [0, 9, 4]:
                task.abort('rtorrent version >=0.9.4 required, found {0}'.format('.'.join(map(str, client.version))))
        except (IOError, xmlrpclib.Error) as e:
            raise plugin.PluginError("Couldn't connect to rTorrent: %s" % str(e))


class RTorrentOutputPlugin(RTorrentPluginBase):

    schema = {
        'type': 'object',
        'properties': {
            # connection info
            'uri': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
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
        for i in range(0, 5):
            try:
                return client.torrent(info_hash, fields=['hash'])
            except (IOError, xmlrpclib.Error):
                sleep(0.5)
        raise

    def on_task_download(self, task, config):
        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

    def on_task_output(self, task, config):
        client = RTorrent(config['uri'], username=config.get('username'), password=config.get('password'))

        for entry in task.accepted:
            if task.options.test:
                log.info('Would add %s to rTorrent' % entry['url'])
                continue

            if config['action'] == 'add':
                options = self._build_options(config, entry)
                self.add_entry(client, entry, options, start=config['start'], mkdir=config['mkdir'])

            info_hash = entry.get('torrent_info_hash')

            if not info_hash:
                entry.fail('Failed to %s as no info_hash found' % (config['action'], entry))
                continue

            if config['action'] == 'delete':
                try:
                    client.delete(info_hash)
                    log.verbose('Deleted %s (%s) in rtorrent ' % (entry['title'], info_hash))
                except (IOError, xmlrpclib.Error) as e:
                    entry.fail('Failed to delete: %s' % str(e))
                    return

            if config['action'] == 'update':
                try:
                    options = self._build_options(config, entry)
                    client.update(info_hash, options)
                    log.verbose('Updated %s (%s) in rtorrent ' % (entry['title'], info_hash))
                except (IOError, xmlrpclib.Error) as e:
                    entry.fail('Failed to update: %s' % str(e))
                    return

    def add_entry(self, client, entry, options, start=True, mkdir=False):

        # Check that file is downloaded
        if 'file' not in entry:
            entry.fail('file missing?')
            return

        # Verify the temp file exists
        if not os.path.exists(entry['file']):
            entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
            return

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
            torrent = Torrent(torrent_raw)
        except SyntaxError as e:
            entry.fail('Strange, unable to decode torrent, raise a BUG: %s' % str(e))
            return

        try:
            resp = client.load(torrent_raw, fields=options, start=start, mkdir=mkdir)
            if resp != 0:
                entry.fail('Failed to add to rTorrent invalid return value %s' % resp)
        except (IOError, xmlrpclib.Error) as e:
            entry.fail('Failed to add to rTorrent %s' % str(e))
            return

        # Verify the torrent loaded
        try:
            self._verify_load(client, torrent.info_hash)
            log.info('%s added to rtorrent' % entry['title'])
        except (IOError, xmlrpclib.Error) as e:
            entry.fail('Failed to verify torrent loaded: %s' % str(e))

    def on_task_exit(self, task, config):
        """ Make sure all temp files are cleaned up when task exists """
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.cleanup_temp_files(task)

    on_task_abort = on_task_exit


class RTorrentInputPlugin(RTorrentPluginBase):

    schema = {
        'type': 'object',
        'properties': {
            'uri': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'view': {'type': 'string', 'default': 'main'},
            'fields': one_or_more({'type': 'string', 'enum': RTorrent.default_fields}),
        },
        'required': ['uri'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        client = RTorrent(config['uri'], username=config.get('username'), password=config.get('password'))

        fields = config.get('fields')

        try:
            torrents = client.torrents(config['view'], fields=fields)
        except (IOError, xmlrpclib.Error) as e:
            task.abort('Could not get torrents (%s): %s' % (config['view'], e))
            return

        entries = []

        for torrent in torrents:
            entry = Entry(
                title=torrent['name'],
                url='%s/%s' % (config['uri'], torrent['hash']),
                path=torrent['directory_base'],
                torrent_info_hash=torrent['hash'],
            )

            for attr, value in torrent.iteritems():
                entry[attr] = value

            entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(RTorrentOutputPlugin, 'rtorrent', api_ver=2)
    plugin.register(RTorrentInputPlugin, 'from_rtorrent', api_ver=2)
