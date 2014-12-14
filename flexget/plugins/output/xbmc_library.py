from __future__ import unicode_literals, division, absolute_import

import os
import logging
import socket
import urlparse
import posixpath
import json

import requests

from flexget.event import event
from flexget import plugin

log = logging.getLogger('xbmc_library')


class XBMCLibrary(object):
    schema = {
        'oneOf': [
            {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['clean', 'scan', 'full_scan']},
                    'category': {'type': 'string', 'enum': ['audio', 'video']},
                    'url': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'dir': {'type': 'string'},
                },
                'required': ['url', 'action', 'category'],
                'additionalProperties': False,
            },
            {
                'type': 'object',
                'properties': {
                    'method': {'type': 'string'},
                    'params': {'type': 'object', 'additionalProperties': True},
                    'url': {'type': 'string'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                },
                'required': ['url', 'method'],
                'additionalProperties': False,
            }
        ]
    }

    # Initialise some variables so we don't have to pass them around everywhere
    def on_task_start(self, task, config):
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.url = config['url']
        self.port = config.get('port', 9090)
        self.authentication_required = True if self.username else False
        self.id = 0
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5)
        self.use_socket = True

    # Ping the XBMC server to test the connection.
    def ping(self):
        # Sends a ping to XBMC. It should respond with 'pong'
        log.info('Pinging XBMC server.')
        try:
            response = self.sendAndRecv('JSONRPC.Ping')
            return response.get('result', '') == 'pong'
        except requests.HTTPError as ex:
            log.error('Connection to XBMC failed: %s.' % ex.args[0])
            return False

    # Takes a string of json objects and returns the json objects in a list
    def decode(self, data):
        _whitespace = json.decoder.WHITESPACE.match
        decoder = json._default_decoder
        idx = _whitespace(data, 0).end()
        end = len(data)
        res = []
        while idx < end:
            (d, idx) = decoder.raw_decode(data, idx=idx)
            idx = _whitespace(data, idx).end()
            res.append(d)
        return res

    # Send a request to XBMC and wait for the result. Currently stopping after receiving "pong" or "SomethingStarted".
    # Could be extended to stop after XBMC notifies about finished jobs, although it can take a while.
    def sendAndRecv(self, method, params=None, use_params=True):
        BUFFER_SIZE = 32768
        self.id += 1
        request = {'id': self.id, 'jsonrpc': '2.0', 'method': method}
        if use_params:
            request['params'] = {} if not params else params
        json_result = {}
        if self.use_socket:
            self.socket.send(json.dumps(request))
            done = False
            while not done:
                try:
                    r = self.socket.recv(BUFFER_SIZE)
                    for json_obj in self.decode(r):
                        m = json_obj.get('method') or json_obj.get('result')
                        if not m:
                            if 'error' in json_obj:
                                log.debug('XBMC Error: %s' % unicode(json_obj['error']['message']))
                                return json_obj
                            continue
                        if m.endswith('Started') or m.endswith('pong'):
                            done = True
                            json_result = json_obj
                except socket.timeout:
                    log.debug('No more data to receive from XBMC.')
                    break
                except ValueError as ex:
                    log.error('Received invalid data: %s.' % ex.args[0])
                    break
        else:
            url = self.url + json.dumps(request)
            if self.authentication_required:
                response = requests.get(url, auth=(self.username, self.password))
            else:
                response = requests.get(url)
            response.raise_for_status()
            json_result = response.json()
        return json_result

    def experimental(self, action, params):
        log.info('Not implemented yet.')
        #log.warning('Attempting experimental feature.')
        pass

    def make_dir_param(self, path):
        if not path.endswith(os.sep):
            path = posixpath.normpath(path) + posixpath.sep
        return {'directory': path}

    @plugin.priority(0)
    def on_task_output(self, task, config):
        if not config:
            return
        action = config.get('action', '')
        category = config['category']
        path = config.get('dir', '')

        try:
            self.socket.connect((self.url, self.port))
        except socket.error as ex:
            log.debug('Unable to connect to socket: %s.' % ex.args[1])
            log.debug('Using XBMC Webserver instead of Websocket.')
            self.use_socket = False
            self.url = urlparse.urljoin(self.url, 'jsonrpc?request=')
            if not self.url.startswith('http://'):
                self.url = 'http://' + self.url

        if not self.ping():
            return
        log.info('Pong.')

        if 'method' in config:
            self.experimental(config['method'], config.get('params', []))
            return
        elif action == 'scan':
            self.scan(category, path, task)
        elif action == 'full_scan':
            self.full_scan(category, path)
        else:
            self.clean(category)
        # Close the socket. Could also just let it be garbage collected.
        if self.use_socket:
            self.socket.shutdown()
            self.socket.close()

    # Library scan. Sends a scan request for every entry in the task. May cause timeouts. Needs more testing.
    def scan(self, category, path, task):
        method = category.title() + 'Library.Scan'
        for entry in task.accepted:
            if 'location' not in entry:
                log.error('Cannot operate on non-local files.')
                entry.fail('Not a local file.')
                continue
            dir_path = entry.render(path)
            if not dir_path:
                if not os.path.exists(entry['location']):
                    entry.fail('File does not exist.')
                    continue
                dir_path = os.path.dirname(entry['location'])
            log.debug('Scanning %s.' % dir_path)
            try:
                response = self.sendAndRecv(method, params=self.make_dir_param(dir_path))
                if not response.get('error', ''):
                    log.info('XBMC is now scanning %s for %s content.' % (dir_path, category))
            except requests.HTTPError as ex:
                log.error('Failed to scan library: %s.' % ex.args[0])

    # Just scan the given path for content.
    def full_scan(self, category, path):
        use_params = False if not path else True
        log.debug('Scanning %s for %s.' % (path, category))
        try:
            response = self.sendAndRecv(category.title() + 'Library.Scan', params=self.make_dir_param(path),
                                 use_params=use_params)
            if not response.get('error', ''):
                log.info('XBMC is now scanning %s for %s content.' % (path, category))
        except requests.HTTPError as ex:
            log.error('Failed to scan library: %s.' % ex.args[0])

    # Cleans the library ie. removes content that is no longer present.
    def clean(self, category):
        try:
            response = self.sendAndRecv(category.title() + 'Library.Clean')
            if not response.get('error'):
                log.info('XBMC is now cleaning the %s library.' % category)
        except requests.HTTPError as ex:
            log.error('Failed to clean library: %s.' % ex.args[0])


@event('plugin.register')
def register_plugin():
    plugin.register(XBMCLibrary, 'xbmc_library', api_ver=2)
