from __future__ import unicode_literals, division, absolute_import
import logging
import socket
import re
import os
import sys
import xmlrpclib
from base64 import encodestring
from urlparse import urlparse
from time import sleep

from flexget import plugin
from flexget.event import event
from flexget.utils.bittorrent import Torrent, is_torrent_file

log = logging.getLogger('rtorrent')

# Methods to call when getting torrent details
torrent_info_methods = (
    "d.get_down_rate",
    "d.get_down_total",
    "d.get_up_rate",
    "d.get_up_total",
    "d.get_directory",
    "d.get_size_bytes",
    "d.get_ratio",
    "d.get_message",
    "d.get_bytes_done",
    "d.get_hashing",
    "d.is_active",
    "d.get_complete",
    "d.is_open",
    "d.get_state",
    "d.get_priority",
    "d.get_base_path",
    "d.get_custom1",
    "d.get_custom2",
    "d.get_custom3",
    "d.get_custom4",
    "d.get_custom5",
)


def to_int(val):
    try:
        return int(val)
    except ValueError:
        return 0


def to_bool(val):
    return bool(to_int(val))


def to_float(val):
    try:
        return float(val)
    except ValueError:
        return 0.0


#TODO: Prob not needed?
def to_str(val):
    return str(val)

# Convert fields from xmlrpc call
field_types = {
    "down_rate": to_int,
    "down_total": to_int,
    "up_rate": to_int,
    "up_total": to_int,
    "directory": to_str,
    "size_bytes": to_int,
    "ratio": to_float,
    "message": to_str,
    "bytes_done": to_int,
    "hashing": to_bool,
    "is_active": to_bool,
    "complete": to_bool,
    "is_open": to_bool,
    "state": to_int,
    "priority": to_int,
    "base_path": to_str,
}

# Allow specifying the priority as a string
priorities = {
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


class BasicAuthTransport(xmlrpclib.Transport):
    """
    Basic Auth for xmlrpc over HTTP
    """
    def __init__(self, username=None, password=None):
        xmlrpclib.Transport.__init__(self)
        self.username = username
        self.password = password

    def send_auth(self, h):
        if self.username and self.password:
            auth_b64 = encodestring("%s:%s" % (self.username, self.password))
            h.putheader('AUTHORIZATION', "Basic %s" % auth_b64)

    def single_request(self, host, handler, request_body, verbose=0):
        # issue XML-RPC request

        h = self.make_connection(host)
        if verbose:
            h.set_debuglevel(1)

        try:
            self.send_request(h, handler, request_body)
            self.send_host(h, host)
            self.send_user_agent(h)
            self.send_auth(h)
            self.send_content(h, request_body)

            response = h.getresponse(buffering=True)
            if response.status == 200:
                self.verbose = verbose
                return self.parse_response(response)
        except xmlrpclib.Fault:
            raise
        except Exception:
            self.close()
            raise

        # discard any response data and raise exception
        if response.getheader("content-length", 0):
            response.read()
        raise xmlrpclib.ProtocolError(
            host + handler,
            response.status, response.reason,
            response.msg,
        )


class RTorrent(object):
    """ Create a new rTorrent connection """

    def __init__(self, uri, username=None, password=None):
        """
        Ingratiate connection to rTorrent

        :param uri: RTorrent URL. Supports both http(s) and scgi
        :param username: Username for basic auth over http(s)
        :param password: Password for basic auth over http(s)
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.schema = urlparse(uri).scheme

        # Determine the proxy server
        if self.schema in ['http', 'https']:
            self._sp = xmlrpclib.ServerProxy
        elif self.schema == 'scgi':
            self._sp = SCGIServerProxy
        else:
            raise IOError("Unsupported scheme %s for uri %s" % (self.schema, self.uri))

        # Setup proxy connection
        if self.username and self.password:
            self._conn = self._sp(self.uri, transport=BasicAuthTransport(self.username, self.password))
        else:
            self._conn = self._sp(self.uri)

    def _call_multi(self, calls):
        """ Build up a multi call over xmlrpc """
        m = xmlrpclib.MultiCall(self._conn)

        for c in calls:
            method = c[0]
            args = c[1]
            if not (isinstance(args, list) or isinstance(args, tuple)):
                args = [args]
            getattr(m, method)(*args)

        return m()

    def get_torrent(self, info_hash):

        calls = [(method, [info_hash]) for method in torrent_info_methods]
        results = self._call_multi(calls)

        # build torrent_info
        torrent_info = {}
        for method, result in zip(torrent_info_methods, results):
            if method.startswith("d.get_"):
                method = method.replace("d.get_", "")
            if method.startswith("d.is_"):
                method = method.replace("d.is_", "")

            if method in field_types:
                result = field_types[method](result)
            torrent_info[method] = result

        try:
            percent = float(torrent_info['bytes_done']) / float(torrent_info['size_bytes']) * 100
        except (ZeroDivisionError, TypeError):
            percent = 0
        torrent_info['percent'] = percent

        # Figure out if torrent is started
        if torrent_info['hashing'] or torrent_info['open'] or torrent_info['active']:
            torrent_info['started'] = True
        else:
            torrent_info['started'] = False

        return torrent_info

    def load_torrent(self, raw_torrent, verbose=False, verify_load=True):
        torrent = Torrent(raw_torrent)
        info_hash = torrent.info_hash

        method = getattr(self._conn, "load_raw_verbose" if verbose else "load_raw")
        method(xmlrpclib.Binary(raw_torrent))

        if verify_load:
            for x in range(0, 3):
                try:
                    self.get_torrent(info_hash)
                    return torrent.info_hash
                except (IOError, xmlrpclib.Fault):
                    sleep(1)

            # Raise last error
            raise

        return torrent.info_hash

    def set_torrent_properties(self, info_hash, props):

        calls = [("d.set_%s" % field, (info_hash, value)) for field, value in props.iteritems()]
        self._call_multi(calls)

    def start(self, info_hash):
        calls = [
            ("d.open", info_hash),
            ("d.start", info_hash),
        ]
        self._call_multi(calls)
        torrent_info = self.get_torrent(info_hash)

        # Sometimes a hash-check is required if the torrent does not start properly
        # This is usually due to files already existing
        # TODO: Is there a better way to do this?
        if not torrent_info['started']:
            calls = [
                ("d.check_hash", info_hash),
                ("d.close", info_hash),
                ("d.stop", info_hash),
                ("d.start", info_hash),
            ]
            self._call_multi(calls)
            torrent_info = self.get_torrent(info_hash)

        return torrent_info['started']


class PluginRTorrent(object):
    """
    Add url from entry url to rTorrent

    Example::

      rtorrent:
        url: scgi://localhost:5000
        username: myusername (http(s) Only)
        password: mypassword (http(s) Only)
        path: the download location

    Default values for the config elements::

      transmission:
        enabled: yes
        url: scgi://localhost:5000
        autostart: yes
        verify: yes
        priority: off
    """

    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'enabled': {'type': 'boolean'},
                    'url': {'type': 'string'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'autostart': {'type': 'boolean'},
                    'verify': {'type': 'boolean'},
                    'path': {'type': 'string'},
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
        config.setdefault('enabled', True)
        config.setdefault('url', 'scgi://localhost:5000')
        config.setdefault('username', None)
        config.setdefault('password', None)
        config.setdefault('autostart', True)
        config.setdefault('verify', True)
        config.setdefault('priority', "off")
        config.setdefault('custom', {})
        return config

    def on_task_start(self, task, config):
        self.client = None
        config = self.prepare_config(config)
        if config['enabled']:
            if task.options.test:
                log.info('Trying to connect to rtorrent...')
                try:
                    self.client = RTorrent(config['url'])
                    log.info('Successfully connected to transmission.')
                except:
                    log.error('It looks like there was a problem connecting to rtorrent.')

    def on_task_download(self, task, config):
        """ Call download plugin to generate the temp files """
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        # If the download plugin is not enabled, we need to call it to get our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

    def on_task_output(self, task, config):
        config = self.prepare_config(config)
        if task.options.learn:
            return
        if not task.accepted:
            return
        if not config['enabled']:
            return

        self.add_to_rtorrent(task, config)

    def add_to_rtorrent(self, task, config):
        try:
            client = RTorrent(config.get('url'))
            log.debug('Successfully connected to rtorrent.')
        except Exception as e:
            raise plugin.PluginError("Couldn't connect to rtorrent.")

        for entry in task.accepted:
            if task.options.test:
                log.info('Would add %s to rtorrent' % entry['url'])
                continue

            # Check that file is downloaded
            if 'file' not in entry:
                entry.fail('file missing?')
                continue

            # Verify the temp file exists
            if not os.path.exists(entry['file']):
                tmp_path = os.path.join(task.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
                continue

            # Verify valid torrent file
            if not is_torrent_file(entry['file']):
                entry.fail("Downloaded temp file '%s' is not a torrent file" % entry['file'])
                continue

            # First load the torrent
            with open(entry['file'], "rb") as f:
                raw_torrent = f.read()

            try:
                info_hash = client.load_torrent(raw_torrent, verify_load=config.get("verify"))
            except (IOError, xmlrpclib.Fault) as e:
                entry.fail("Error loading torrent %s" % str(e))
                continue

            # Build up a multi call to set properties of torrent
            props = {"priority": priorities[config.get("priority", "off")]}

            # Try set the save folder. Use path if directory is not set
            if config.get("path"):
                props['directory'] = config.get("path")
            elif entry.get('path'):
                props['directory'] = entry['path']

            # custom fields
            for i in range(1, 4):
                if config.get("custom%s" % i):
                    props["custom%s" % i] = config["custom%s" % i]

            # TODO: Add support for include/exclude files and change their priorities

            try:
                client.set_torrent_properties(info_hash, props)
            except (IOError, xmlrpclib.Fault) as e:
                entry.fail("Error setting properties of torrent %s" % str(e))
                continue

            if config.get("autostart"):
                # Ensure torrent was started
                try:
                    started = client.start(info_hash)
                    if not started:
                        entry.fail("Torrent didn't start")
                        continue
                except (IOError, xmlrpclib.Fault) as e:
                    entry.fail("Error starting torrent %s" % str(e))
                    continue

            log.info('"%s" torrent added to rtorrent' % (entry['title']))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginRTorrent, 'rtorrent', api_ver=2)