from __future__ import unicode_literals, division, absolute_import

import os
import logging
import urlparse

import requests

from flexget.event import event
from flexget import plugin
from flexget.utils import json

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

    def on_task_input(self, task, config):
        self.on_task_output(task, config)

    def on_task_start(self, task, config):
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.url = urlparse.urljoin(config['url'], 'jsonrpc?request=')
        if not self.url.startswith('http://'):
            self.url = 'http://' + self.url
        self.authentication_required = True if self.username else False
        self.id = 0

    def ping(self):
        # Sends a ping to XBMC. It should respond with 'pong'
        log.info('Pinging XBMC server.')
        try:
            response = self.send('JSONRPC.Ping')
            return response.json().get('result', '') == 'pong'
        except requests.HTTPError as ex:
            log.error('Connection to XBMC failed: %s.' % ex.args[0])
            return False

    def send(self, method, params=None, use_params=True):
        self.id += 1
        msg = {'id': self.id, 'jsonrpc': '2.0', 'method': method}
        if use_params:
            msg['params'] = [] if not params else params

        url = self.url + json.dumps(msg)
        if self.authentication_required:
            response = requests.get(url, auth=(self.username, self.password))
        else:
            response = requests.get(url)
        response.raise_for_status()
        return response

    def experimental(self, action, params):
        log.info('Not implemented yet.')
        #log.warning('Attempting experimental feature.')
        pass

    def on_task_output(self, task, config):
        if not config:
            return
        action = config.get('action', '')
        category = config['category']
        path = config.get('dir', '')

        if not self.ping():
            return

        if 'method' in config:
            self.experimental(config['method'], config.get('params', []))
            return
        elif action == 'scan':
            self.scan(category, path, task)
        elif action == 'full_scan':
            self.full_scan(category, path)
        else:
            self.clean(category)

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
                response = self.send(method, params=[dir_path])
                response_json = response.json()
                if response_json.get('result', '') != 'OK' or response_json.get('error', ''):
                    log.error('XBMC Error: %s' % unicode(response_json['error']['message']))
                else:
                    log.info('Successfully scanned %s for %s content.' % (path, category))
            except requests.HTTPError as ex:
                log.error('Failed to scan library: %s.' % ex.args[0])

    def full_scan(self, category, path):
        # if not os.path.exists(path):
        #     log.error('Directory does not exist: %s.' % path)
        #     return
        use_params = False if not path else True
        log.debug('Scanning %s.' % path)
        try:
            response = self.send(category.title() + 'Library.Scan', params=[path], use_params=use_params)
            response_json = response.json()
            if response_json.get('result', '') != 'OK' or response_json.get('error', ''):
                log.debug('XBMC Error: %s' % unicode(response_json['error']['message']))
            else:
                log.info('Successfully scanned %s for %s content.' % (path, category))
        except requests.HTTPError as ex:
            log.error('Failed to scan library: %s.' % ex.args[0])

    def clean(self, category):
        try:
            response = self.send(category.title() + 'Library.Clean')
            response_json = response.json()
            if response_json.get('result', '') != 'OK' or response_json.get('error', ''):
                log.debug('XBMC Error: %s' % unicode(response_json['error']['message']))
            else:
                log.info('Successfully cleaned the XBMC %s library.' % category)
        except requests.HTTPError as ex:
            log.error('Failed to clean library: %s.' % ex.args[0])


@event('plugin.register')
def register_plugin():
    plugin.register(XBMCLibrary, 'xbmc_library', api_ver=2)
