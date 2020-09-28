from loguru import logger

from flexget import log, plugin
from flexget.event import event

logger = logger.bind(name='log_filter')


class MyFilter:
    def __init__(self, config):
        self.config = config

    def __call__(self, record):
        for plugin_name, filter_strings in self.config.items():
            for filter_string in filter_strings:
                if record['name'] == plugin_name and filter_string in record['message']:
                    return False
        return True


class LogFilter(object):
    """
    Prevent entries with specific text from being logged.

    Example::
      log_filter:
        some.context:
          - in a galaxy
          - far far away
        another.context:
          - whatever text
          - what the heck?

    """

    schema = {
        'type': 'object',
        'additionalProperties': {
            'type': 'array',
            'items': {'type': 'string'},
            'minItems': 1,
            'additionalProperties': 'string',
        },
    }

    @plugin.priority(255)
    def on_task_start(self, task, config):
        task.log_filter = MyFilter(config)
        log.add_filter(task.log_filter)
        logger.debug('Log filter added (config: {})', config)

    @plugin.priority(-255)
    def on_task_exit(self, task, config):
        if getattr(task, 'log_filter', None):
            log.remove_filter(task.log_filter)
            del task.log_filter

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(LogFilter, 'log_filter', api_ver=2)
