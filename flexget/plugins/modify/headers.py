from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='headers')


class PluginHeaders:
    """Allow setting up any headers in all requests (which use urllib2)

    Example:

    headers:
      cookie: uid=<YOUR UID>; pass=<YOUR PASS>
    """

    schema = {'type': 'object', 'additionalProperties': {'type': 'string'}}

    @plugin.priority(130)
    def on_task_start(self, task, config):
        """Task starting"""
        # Set the headers for this task's request session
        logger.debug('headers to add: {}', config)
        if task.requests.headers:
            task.requests.headers.update(config)
        else:
            task.requests.headers = config


@event('plugin.register')
def register_plugin():
    plugin.register(PluginHeaders, 'headers', api_ver=2)
