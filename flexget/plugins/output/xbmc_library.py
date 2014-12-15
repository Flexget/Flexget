from __future__ import unicode_literals, division, absolute_import

import os
import logging
import socket
import urlparse
import posixpath
import json
import select

import requests

from flexget.event import event
from flexget import plugin

log = logging.getLogger('xbmc_library')

# Inspired by MilhouseVH's texturecache https://github.com/MilhouseVH/texturecache.py
class XBMCLibrary(object):
    schema = {
        'oneOf': [
            {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['clean', 'scan', 'dir_scan']},
                    'category': {'type': 'string', 'enum': ['audio', 'video']},
                    'url': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'dir': {'type': 'string'},
                    'use_socket': {'type': 'boolean', 'default': False}
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
        self.socket = None
        self.use_socket = config['use_socket']
        self.lookup_socket = None
        self.BUFFER_SIZE = 32768
        self.count = 0

    # Ping the XBMC server to test the connection.
    def ping(self):
        # Sends a ping to XBMC. It should respond with 'pong'
        log.debug('Pinging XBMC server.')
        try:
            response = self.sendAndRecv({'method': 'JSONRPC.Ping'}, handler=self.pong)
            return response.get('result', '') == 'pong'
        except requests.HTTPError as ex:
            log.error('Connection to XBMC failed: %s.' % ex.args[0])
            return False

    def pong(self, json_results):
        for json_obj in json_results:
            res = json_obj.get('result')
            if not res:
                if 'error' in json_obj:
                    log.debug('XBMC Error: %s' % unicode(json_obj['error']['message']))
                    return json_obj
                continue
            if res == 'pong':
                return json_obj

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
    def sendAndRecv(self, request, handler=None):
        self.id += 1
        request['id'] = self.id
        request['jsonrpc'] = '2.0'
        json_result = {}
        if self.use_socket:
            self.socket.send(json.dumps(request))
            done = False
            while not done:
                try:
                    self.socket.setblocking(0)
                    read = select.select([self.socket], [], [], 60.0)
                    if read[0]:
                        response = self.socket.recv(self.BUFFER_SIZE)
                        if handler:
                            json_result = handler(self.decode(response))
                            if json_result:
                                done = True
                        else:
                            return self.decode(response)
                    else:
                        break
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

        if self.use_socket:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self.url, self.port))
                self.socket.setblocking(0)
            except socket.error as ex:
                log.debug('Unable to connect to socket: %s.' % ex.args[1])
                log.debug('Using XBMC Webserver instead of Websocket.')
                self.use_socket = False
                self.url = urlparse.urljoin(self.url, 'jsonrpc?request=')
                if not self.url.startswith('http://'):
                    self.url = 'http://' + self.url

        if not self.ping():
            return
        log.debug('Pong.')

        if 'method' in config:
            self.experimental(config['method'], config.get('params', []))
            return
        elif action == 'scan':
            self.scan(category, path, task)
        elif action == 'dir_scan':
            self.dir_scan(category, path)
        else:
            self.clean(category)

    # very ugly function that creates a second socket and attempts to get content information from XBMC
    # it then logs any information it receives.
    def log_item(self, type, id):
        if not self.lookup_socket:
            try:
                self.lookup_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.lookup_socket.connect((self.url, self.port))
            except Exception as ex:
                log.error('Failed to lookup item id %s: %s.' % (id, ex.args[0]))
        try:
            types = {'song': 'Song', 'movie': 'Movie', 'episode': 'Episode', 'tvshow': 'TVShow',
                     'musicvideo': 'MusicVideo'}
            request = {}
            request['jsonrpc'] = '2.0'
            self.id += 1
            request['id'] = self.id

            # Choose method.
            method = 'VideoLibrary.Get'
            if type == 'song':
                method = 'AudioLibrary.Get'
            method += types[type] + 'Details'
            request['method'] = method

            # Params
            params = {type + 'id': id, 'properties': ['title']}
            if type == 'episode':
                params['properties'].extend(['showtitle', 'season', 'episode'])
            request['params'] = params

            # connect as late as possible to avoid unnecessary notifications
            self.lookup_socket.setblocking(1)
            self.lookup_socket.send(json.dumps(request))
            self.lookup_socket.setblocking(0)
            while True:
                read = select.select([self.lookup_socket], [], [], 10.0)
                if read[0]:
                    data = self.decode(self.lookup_socket.recv(self.BUFFER_SIZE))
                    details = type + 'details'
                    for item in data:
                        if 'result' in item and details in item['result']:
                            info = item['result'][details]
                            if type == 'episode':
                                log.debug("Update: XBMC library: %s S%02dE%02d (%s)" %
                                         (info['showtitle'], info['season'], info['episode'], type))
                            else:
                                log.debug("Update: XBMC library: %s (%s)" % (info['title'], type))
                            return
                else:
                    break
        except Exception as ex:
            log.error('Failed to lookup item id %s: %s.' % (id, ex.args[0]))
            return

    def parse_response(self, json_results):
        for json_obj in json_results:
            method = json_obj.get('method', '')
            if method.endswith('Library.OnUpdate'):
                params = json_obj['params']
                if 'data' not in params and 'item' not in params['data']:
                    continue
                else:
                    data = params['data']
                    type = data.get('type', data.get('item', {}).get('type'))
                    if type == 'tvshow':
                        continue  # skip logging this. Not interesting.
                    id = data.get('id', data.get('item', {}).get('id'))
                    self.log_item(type, id)
                    self.count += 1
            elif method.endswith('Library.OnRemove'):
                # Odds are the items are no longer in XBMC and so lookups are useless.
                self.count += 1
            elif method.endswith('Library.OnScanFinished'):
                log.info('XBMC library scan complete. Added %s items.' % self.count)
                return json_obj
            elif method.endswith('Library.OnCleanFinished'):
                log.info('XBMC library clean complete. Removed %s items.' % self.count)
                return json_obj
            elif 'error' in json_obj:
                log.debug(json_obj['error']['message'])
                return json_obj
            continue

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
                request = {'method': method, 'params': self.make_dir_param(dir_path)}
                response = self.sendAndRecv(request, handler=self.parse_response)
                if not response:
                    log.info('Slow response from XBMC. It may be busy.')
                elif response.get('error', ''):
                    log.error('ERROR: %s.' % response.get('error')['message'])
            except requests.HTTPError as ex:
                log.error('Failed to scan library: %s.' % ex.args[0])

    # Just scan the given path for content.
    def dir_scan(self, category, path):
        log.info('Scanning %s for %s.' % (path, category))
        try:
            request = {'method': category.title() + 'Library.Scan', 'params': self.make_dir_param(path)}
            response = self.sendAndRecv(request, handler=self.parse_response)
            if not response:
                log.info('Slow response from XBMC. It may be busy.')
            elif response.get('error', ''):
                log.error('ERROR: %s.' % response.get('error')['message'])
        except requests.HTTPError as ex:
            log.error('Failed to scan library: %s.' % ex.args[0])

    # Cleans the library ie. removes content that is no longer present.
    def clean(self, category):
        try:
            request = {'method': category.title() + 'Library.Clean'}
            response = self.sendAndRecv(request, handler=self.parse_response)
            if not response:
                log.debug('Slow response from XBMC. It may be busy.')
            elif response.get('error', ''):
                log.debug('ERROR: %s.' % response.get('error')['message'])
        except requests.HTTPError as ex:
            log.error('Failed to clean library: %s.' % ex.args[0])


@event('plugin.register')
def register_plugin():
    plugin.register(XBMCLibrary, 'xbmc_library', api_ver=2)
