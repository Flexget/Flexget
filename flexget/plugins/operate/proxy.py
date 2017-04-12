from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import os

from flexget import plugin
from flexget.event import event

log = logging.getLogger('proxy')

PROTOCOLS = ['http', 'https', 'ftp', 'socks5']


class Proxy(object):
    """Adds a proxy to the requests session."""

    schema = {
        'oneOf': [
            {'type': 'string', 'format': 'url'},
            {
                'type': 'object',
                'properties': dict((prot, {'type': 'string', 'format': 'url'}) for prot in PROTOCOLS),
                'additionalProperties': False
            }
        ]
    }

    @plugin.priority(255)
    def on_task_start(self, task, config):
        if not config:
            # If no configuration is provided, see if there are any proxy env variables
            proxies = {}
            for prot in PROTOCOLS:
                if os.environ.get(prot + '_proxy'):
                    proxies[prot] = os.environ[prot + '_proxy']
            if not proxies:
                # If there were no environment variables set, do nothing
                return
        elif isinstance(config, dict):
            proxies = config
        else:
            # Map all protocols to the configured proxy
            proxies = dict((prot, config) for prot in PROTOCOLS)
        log.verbose('Setting proxy to %s', proxies)
        task.requests.proxies = proxies


@event('plugin.register')
def register_plugin():
    plugin.register(Proxy, 'proxy', builtin=True, api_ver=2)
