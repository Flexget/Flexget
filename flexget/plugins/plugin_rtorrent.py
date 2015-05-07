from __future__ import unicode_literals, division, absolute_import
import logging

import sys
import os
import socket
import re
from time import sleep
from urlparse import urlparse

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.pathscrub import pathscrub
from flexget.utils.template import RenderError
from flexget.utils.bittorrent import Torrent, is_torrent_file


import xmlrpclib


log = logging.getLogger('rtorrent')


priority_map = {
    "high": 3,
    "medium": 2,
    "low": 1,
    "off": 0,
}


class SCGITransport(xmlrpclib.Transport):
    """
    Used to override the default xmlrpclib transport to support SCGI
    """

    def request(self, host, handler, request_body, verbose=0):
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
                sock.send(bytes(request_body, "utf-8"))
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

        # Remove SCGI headers from the response.

        if self.verbose:
            print('body:', repr(response_body))

        response_header, response_body = re.split(r'\n\s*?\n', response_body, maxsplit=1)
        p.feed(response_body)
        p.close()

        return u.close()


class SCGIServerProxy(xmlrpclib.ServerProxy):
    """
    Enable connection to SCGI proxy
    """

    def __init__(self, uri, transport=None, encoding=None, verbose=False, allow_none=False, use_datetime=False):
        parsed_uri = urlparse(uri)
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
        response = self.__transport.request(self.__host, self.__handler, request, verbose=self.__verbose)

        if len(response) == 1:
            response = response[0]

        return response

    def __repr__(self):
        return "<SCGIServerProxy for %s%s>" % (self.__host, self.__handler)

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
        if attr == "close":
            return self.__close
        elif attr == "transport":
            return self.__transport
        raise AttributeError("Attribute %r not found" % (attr,))


class Rtorrent(object):
    """ rTorrent API client """

    default_fields = [
        'hash',
        'name',
        'up.total', 'down.total',
        'is_open', 'is_active',
        'custom1', 'custom2', 'custom3', 'custom4', 'custom5',
        'state', 'complete',
        'ratio',
        'directory', 'directory_base'
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

        # Reformat uri with username and password
        if self.username and self.password:
            data = {
                "scheme": parsed_uri.scheme,
                "hostname": parsed_uri.hostname,
                "port": parsed_uri.port,
                "path": parsed_uri.path,
                "query": parsed_uri.query,
                "username": self.username,
                "password": self.password,
            }
            self.uri = "%(scheme)s://%(username)s:%(password)s@%(hostname)s%(path)s%(query)s" % data

        # Determine the proxy server
        if parsed_uri.scheme in ['http', 'https']:
            sp = xmlrpclib.ServerProxy
        elif parsed_uri.scheme == 'scgi':
            sp = SCGIServerProxy
        else:
            raise IOError("Unsupported scheme %s for uri %s" % (parsed_uri.scheme, self.uri))

        self.server = sp(self.uri)

    @property
    def version(self):
        return [int(v) for v in self.server.system.client_version().split(".")]

    def load(self, torrent, options={}, start=False, mkdir=True):
        if os.path.isfile(torrent):
            load_method = 'load.raw' + ('_start' if start else '')

            # TODO: pass data directly, rather than have this rely on the filesystem
            with open(torrent, 'rb') as f:
                torrent = xmlrpclib.Binary(f.read())
        else:
            load_method = 'load.' + ('start' if start else 'normal')

        # First param is empty 'target'
        params = ['', torrent]

        # Additional commands
        for key, val in options.iteritems():
            params.append('d.{0}.set={1}'.format(key, val))

        if mkdir and 'directory' in options:
            # TODO: execute this and load_method in a MultiCall
            result = self.server.execute.throw('', "mkdir", "-p", options['directory'])
            if result != 0:
                raise xmlrpclib.Error("Failed creating directory {0}".format(options['directory']))

        # Call method and return the response
        return getattr(self.server, load_method)(*params)

    def torrent(self, info_hash, fields=None):
        if not fields:
            fields = self.default_fields

        multi_call = xmlrpclib.MultiCall(self.server)

        for field in fields:
            method_name = 'd.{0}'.format(field)
            getattr(multi_call, method_name)(info_hash)

        resp = multi_call()
        return dict(zip(fields, resp.results))

    def torrents(self, view='main', fields=None):
        if not fields:
            fields = self.default_fields
        params = ['d.{0}='.format(field) for field in fields]
        params.insert(0, view)

        resp = self.server.d.multicall(params)
        # Response is formatted as a list of lists, with just the values
        return [dict(zip(fields, val)) for val in resp]

    def verify_load(self, info_hash, delay=0.5, attempts=3):
        for i in range(0, attempts):
            try:
                # TODO: verify this works as expected
                return info_hash == self.server.d.hash(info_hash)
            except Exception as e:
                sleep(delay)
        raise


class RtorrentPluginBase(object):

    def on_task_start(self, task, config):
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        client = Rtorrent(config['uri'])
        try:
            if client.version < [0, 9, 4]:
                task.abort("rtorrent version >=0.9.4 required, found {0}".format('.'.join(map(str, client.version))))
        except (IOError, xmlrpclib.Error) as e:
            raise plugin.PluginError("Couldn't connect to rtorrent: %s" % str(e))


class RtorrentOutputPlugin(RtorrentPluginBase):

    schema = {
        'anyOf': [
            # allow construction with just a bool for enabled
            {'type': 'boolean'},
            # allow construction with just a URI
            {'type': 'string'},
            # allow construction with options
            {
                'type': 'object',
                'properties': {
                    'enabled': {'type': 'boolean'},
                    # connection info
                    'uri': {'type': 'string'},
                    # handling options
                    'start': {'type': 'boolean'},
                    # properties to set on rtorrent download object
                    'message': {'type': 'string'},
                    'directory': {'type': 'string'},
                    'directory_base': {'type': 'string'},
                    'priority': {'type': 'string'},
                    'custom1': {'type': 'string'},
                    'custom2': {'type': 'string'},
                    'custom3': {'type': 'string'},
                    'custom4': {'type': 'string'},
                    'custom5': {'type': 'string'},
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        if isinstance(config, str):
            config = {'uri': config}

        config.setdefault('enabled', True)
        config.setdefault('uri', 'scgi://localhost:5000')
        config.setdefault('start', True)

        return config

    def _build_options(self, config, entry):
        options = {}

        for opt_key in ('directory', 'directory_base', 'message', 'priority',
                        'custom1', 'custom2', 'custom3', 'custom4', 'custom5'):
            # Values do not merge config with task
            # Task takes priority then config is used
            if opt_key in entry:
                options[opt_key] = entry[opt_key]
            elif opt_key in config:
                options[opt_key] = config[opt_key]

        # Convert priority from string to int
        if options.get('priority'):
            priority = options['priority']
            if priority in priority_map:
                options['priority'] = priority_map[priority]

        return options

    def on_task_download(self, task, config):
        """
        Call download plugin to generate the temp files 
        we will load in client.
        """
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

    def on_task_output(self, task, config):
        """This method is based on Transmission plugin's implementation"""
        config = self.prepare_config(config)
        if not config['enabled']:
            return
        if task.options.learn:
            return
        if not task.accepted:
            return
        
        client = Rtorrent(config['uri'])

        for entry in task.accepted:
            if task.options.test:
                log.info('Would add {0} to rTorrent'.format(entry['url']))
                continue

            # TODO: Should this be moved to the add_entry_to_client method?
            tmp_path = os.path.join(task.manager.config_base, 'temp')
            options = self._build_options(config, entry)

            self.add_entry_to_client(client, entry, options, tmp_path, start=config['start'])

    def add_entry_to_client(self, client, entry, options, tmp_path, start=True):
        downloaded = not entry['url'].startswith('magnet:')

        # Check that file is downloaded
        if downloaded and 'file' not in entry:
            entry.fail('file missing?')
            return

        # Verify the temp file exists
        if downloaded:
            if not os.path.exists(entry['file']):
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
                return

            # Verify valid torrent file
            if not is_torrent_file(entry['file']):
                entry.fail("Downloaded temp file '%s' is not a torrent file" % entry['file'])
                return

        torrent = entry['file'] if downloaded else entry['url']

        try:
            client.load(torrent, options, start=start)
        except (IOError, xmlrpclib.Error) as e:
            entry.fail('Failed to add: {0}'.format(e))
            return

        if 'torrent_info_hash' not in entry:
            log.info('Cannot verify add: we have no info-hash')
            return

        try:
            client.verify_load(entry['torrent_info_hash'])
            log.info("{0} added to rtorrent".format(entry['title']))
        except (IOError, xmlrpclib.Error) as e:
            entry.fail('Failed to verify torrent loaded: {0}'.format(str(e)))

    def on_task_exit(self, task, config):
        """Make sure all temp files are cleaned up when task exists"""
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.cleanup_temp_files(task)

    on_task_abort = on_task_exit


class RtorrentInputPlugin(RtorrentPluginBase):

    schema = {
        'anyOf': [
            # allow construction with just a bool for enabled
            {'type': 'boolean'},
            # allow construction with just a URI
            {'type': 'string'},
            # allow construction with options
            {
                'type': 'object',
                'properties': {
                    'enabled': {'type': 'boolean'},
                    # connection info
                    'uri': {'type': 'string'},
                    # additional options
                    'view': {'type': 'string'},
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        if isinstance(config, str):
            config = {'uri': config}

        config.setdefault('enabled', True)
        config.setdefault('uri', 'scgi://localhost:5000')
        config.setdefault('view', 'main')

        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        client = Rtorrent(config['uri'])

        try:
            torrents = client.torrents(config['view'])
        except (IOError, xmlrpclib.Error) as e:
            task.abort('Could not get torrents: {0}'.format(e))
            return

        entries = []
        for torrent in torrents:
            # TODO: add other fields like trackers, file, etc.
            entry = Entry(
                title=torrent['name'],
                torrent_info_hash=torrent['hash'],
                path=torrent['directory_base'],
                url="%s/%s" % (config['uri'], torrent['hash']),
            )
            for attr in ['custom1', 'custom2', 'custom3', 'custom4', 'custom5']:
                entry['rtorrent_' + attr] = torrent[attr]

            entries.append(entry)

        return entries



@event('plugin.register')
def register_plugin():
    plugin.register(RtorrentOutputPlugin, 'rtorrent', api_ver=2)
    plugin.register(RtorrentInputPlugin, 'from_rtorrent', api_ver=2)
    # plugin.register(RtorrentCleanupPlugin, 'clean_rtorrent', api_ver=2)
