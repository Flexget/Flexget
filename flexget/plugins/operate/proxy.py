from __future__ import unicode_literals, division, absolute_import
import logging
import os

from flexget import plugin
from flexget import validator

log = logging.getLogger('proxy')

PROTOCOLS = ['http', 'https', 'ftp']


class Proxy(object):
    """Adds a proxy to the requests session."""

    def validator(self):
        root = validator.factory()
        # Accept one proxy for everything
        root.accept('url')
        # Accept a dict mapping protocol to proxy
        advanced = root.accept('dict')
        for prot in PROTOCOLS:
            advanced.accept('url', key=prot)
        return root

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
        log.verbose('Setting proxy to %s' % proxies)
        task.requests.proxies = proxies


plugin.register_plugin(Proxy, 'proxy', builtin=True, api_ver=2)
