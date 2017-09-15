from __future__ import unicode_literals, division, absolute_import

import re
import logging

from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from flexget import plugin
from flexget.event import event

PLUGIN_NAME = 'download_auth'

log = logging.getLogger(PLUGIN_NAME)


class DownloadAuth(object):
    host_schema = {
        'additionalProperties': {
            'type': 'object',
            'properties': {
                'username': {'type': 'string'},
                'password': {'type': 'string'},
                'type': {
                    'type': 'string',
                    'enum': ['basic', 'digest'],
                    'default': 'basic'
                }
            },
            'required': ['username', 'password']
        }
    }
    schema = {
        'type': 'array',
        'items': host_schema,
        'minimumItems': 1
    }

    auth_mapper = {
        'basic': HTTPBasicAuth,
        'digest': HTTPDigestAuth
    }

    # Run before all downloads
    @plugin.priority(255)
    def on_task_download(self, task, config):
        for entry in task.accepted:
            if entry.get('download_auth'):
                log.debug('entry %s already has auth set, skipping', entry)
                continue
            for host_config in config:
                for host, auth_config in host_config.items():
                    if re.search(host, entry['url'], re.IGNORECASE):
                        auth_type = auth_config['type']
                        username = auth_config['username']
                        password = auth_config['password']
                        log.debug('setting auth type %s with username %s', auth_type, username)
                        entry['download_auth'] = self.auth_mapper[auth_type](username, password)


@event('plugin.register')
def register_plugin():
    plugin.register(DownloadAuth, PLUGIN_NAME, api_ver=2)
