from __future__ import unicode_literals, division, absolute_import

import os
import logging
import urlparse

from requests import codes

from flexget.event import event
from flexget import plugin
from flexget.task import TaskAbort
from flexget.utils import requests
from flexget.utils import json

log = logging.getLogger('xbmc_library')


class XBMCLibrary(object):
    schema = {
        'oneOf': [
            {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': {'clean', 'scan', 'full_scan'}},
                    'category': {'type': 'string', 'enum': {'audio', 'video'}},
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
        self.authentication_required = True if self.username else False
        self.id = 0

    def ping(self):
        # Sends a ping to XBMC. It should respond with 'pong'
        log.info('Pinging XBMC server.')
        return self.send('JSONRPC.Ping').get('result', '') == 'pong'

    def send(self, method, params=None, use_params=True):
        self.id += 1
        msg = {'id': self.id, 'jsonrpc': '2.0', 'method': method}
        if use_params:
            msg['params'] = [] if not params else params

        url = self.url + msg
        if self.authentication_required:
            request = requests.get(url, auth=(self.username, self.password))
        else:
            request = requests.get(url)
        return request

    def experimental(self, action, params):
        log.warning('Attempting experimental feature.')
        pass

    def on_task_output(self, task, config):
        if not config:
            return
        action = config.get('action', '')
        category = config['category']
        path = config.get('path', '')

        if not self.ping():
            log.error('Could not connect to XBMC server. Please check your configs.')
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
            request = self.send(method, params=[dir_path])
            rjson = request.json()
            if request.status_code != codes.ok or rjson.get('result', '') != 'OK':
                log.error('Failed to scan %s library.' % category)
                if rjson.get('error', ''):
                    log.debug('XBMC Error: %s' % unicode(rjson['error']['message']))
            else:
                log.info('Successfully scanned %s for %s content.' % (path, category))

    def full_scan(self, category, path):
        if not os.path.exists(path):
            log.error('Directory does not exist: %s.' % path)
            return
        use_params = False if not path else True
        request = self.send(category.title() + 'Library.Scan', params=[path], use_params=use_params)
        rjson = request.json()
        if request.status_code != codes.ok or rjson.get('result', '') != 'OK':
            log.error('Failed to scan %s library.' % category)
            if rjson.get('error', ''):
                log.debug('XBMC Error: %s' % unicode(rjson['error']['message']))
        else:
            log.info('Successfully scanned %s for %s content.' % (path, category))

    def clean(self, category):
        request = self.send(category.title() + 'Library.Clean')
        rjson = request.json()
        if request.status_code != codes.ok or rjson.get('result', '') != 'OK':
            log.error('Failed to clean library.')
            if rjson.get('error', ''):
                log.debug('XBMC Error: %s' % unicode(rjson['error']['message']))
        else:
            log.info('Successfully cleaned the XBMC %s library.' % category)


@event('plugin.register')
def register_plugin():
    plugin.register(XBMCLibrary, 'xbmc_library', api_ver=2)