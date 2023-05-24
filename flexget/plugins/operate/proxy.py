import os

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='proxy')

PROTOCOLS = ['http', 'https']


class Proxy:
    """Adds a proxy to the requests session."""

    schema = {
        'oneOf': [
            {'type': 'string', 'format': 'url'},
            {
                'type': 'object',
                'properties': {prot: {'type': 'string', 'format': 'url'} for prot in PROTOCOLS},
                'additionalProperties': False,
            },
        ]
    }

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_prepare(self, task, config):
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
            proxies = {prot: config for prot in PROTOCOLS}
        logger.verbose('Setting proxy to {}', proxies)
        task.requests.proxies = proxies


@event('plugin.register')
def register_plugin():
    plugin.register(Proxy, 'proxy', builtin=True, api_ver=2)
