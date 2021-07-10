import os
from loguru import logger
from requests import Session
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError
from os import error
from requests import Session
from loguru import logger
import json
import base64

logger = logger.bind(name='flood')

class OutputFlood:
    schema = {
       'type': 'object',
        'properties': {
            'host': {'type': 'string'},
            'port': {'type': 'integer'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'directory': {'type': 'string'},
            'tags': {'type': 'array'},
        },
        'additionalProperties': False,
    }

    def __init__(self):
        self.session = Session()
        self.connected = False

    def _request(self, method, url, **kwargs):
        try:
            return self.session.request(method, url, **kwargs)
        except RequestException as e:
            raise plugin.PluginError(f'Flood Request Exception: {e}')
    
    def authenticate(self, config):
        response = self._request('post', '{}:{}/api/auth/authenticate'.format(config['host'], config['port']), data={
            'username': config['username'],
            'password': config['password']
        })

        if 'Failed login.' in response.text:
            raise plugin.PluginError('Incorrect username or password')
        else:
            logger.debug('Successfully logged into Flood')
            self.connected = True
        return self.connected

    """// POST /api/torrents/add-urls
    export const addTorrentByURLSchema = object({
      // URLs to download torrents from
      urls: array(string()).nonempty(),
      // Cookies to attach to requests, arrays of strings in the format "name=value" with domain as key
      cookies: record(array(string())).optional(),
      // Path of destination
      destination: string().optional(),
      // Tags
      tags: array(string().regex(noComma, TAG_NO_COMMA_MESSAGE)).optional(),
      // Whether destination is the base path [default: false]
      isBasePath: boolean().optional(),
      // Whether destination contains completed contents [default: false]
      isCompleted: boolean().optional(),
      // Whether contents of a torrent should be downloaded sequentially [default: false]
      isSequential: boolean().optional(),
      // Whether to use initial seeding mode [default: false]
      isInitialSeeding: boolean().optional(),
      // Whether to start torrent [default: false]
      start: boolean().optional(),
    });"""
    def add_torrent_urls(self, config, urls):
        if not self.connected:
            raise plugin.PluginError('Not connected.')

        response = self._request('post', '{}:{}/api/torrents/add-urls'.format(config['host'], config['port']), json={
            'urls': urls,
            'destination': config['directory'],
            'tags': config['tags'],
            'start': True
        })

        if response.status_code == 200:
            logger.debug('Successfully added torrent to Flood')
        else:
            raise plugin.PluginError('Failed to add torrent to Flood. Error {}'.format(response.status_code))

    """// POST /api/torrents/add-files
    export const addTorrentByFileSchema = object({
    // Torrent files in base64
    files: array(string()).nonempty(),
    // Path of destination
    destination: string().optional(),
    // Tags
    tags: array(string().regex(noComma, TAG_NO_COMMA_MESSAGE)).optional(),
    // Whether destination is the base path [default: false]
    isBasePath: boolean().optional(),
    // Whether destination contains completed contents [default: false]
    isCompleted: boolean().optional(),
    // Whether contents of a torrent should be downloaded sequentially [default: false]
    isSequential: boolean().optional(),
    // Whether to use initial seeding mode [default: false]
    isInitialSeeding: boolean().optional(),
    // Whether to start torrent [default: false]
    start: boolean().optional(),
    });"""
    def add_torrent_files(self, config, data):
        if not self.connected:
            raise error('Not connected')

        response = self._request('post', '{}:{}/api/torrents/add-files'.format(config['host'], config['port']), json=data)

        if response.status_code == 200:
            logger.debug('Successfully added torrent to Flood')
        else:
            raise plugin.PluginError('Failed to add torrent to Flood. Error {}'.format(response.status_code))

    #@plugin.priority(120)
    #def on_task_download(self, task, config):

    @plugin.priority(135)
    def on_task_output(self, task, config):
        if task.accepted and self.authenticate(config):
            self.add_torrent_urls(config, [entry['url'] for entry in task.accepted])

@event('plugin.register')
def register_plugin():
    plugin.register(OutputFlood, 'flood', api_ver=2)
