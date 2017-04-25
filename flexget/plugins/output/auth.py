from __future__ import unicode_literals, division, absolute_import

import logging

from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from flexget import plugin
from flexget.event import event

PLUGIN_NAME = 'auth'

log = logging.getLogger(PLUGIN_NAME)


class RequestAuth(object):
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['basic', 'digest'], 'default': 'basic'}
        },
        'required': ['username', 'password'],
        'additionalProperties': False
    }

    auth_mapper = {
        'basic': HTTPBasicAuth,
        'digest': HTTPDigestAuth
    }

    # Run before all downloads
    @plugin.priority(255)
    def on_task_download(self, task, config):
        auth_type = config['type']
        username = config['username']
        password = config['password']

        for entry in task.accepted:
            if entry.get('download_auth'):
                log.verbose('entry %s already has auth set, skipping', entry)
                continue
            log.debug('setting auth type %s with username %s', auth_type, username)
            entry['download_auth'] = self.auth_mapper[auth_type](username, password)


@event('plugin.register')
def register_plugin():
    plugin.register(RequestAuth, PLUGIN_NAME, api_ver=2)
