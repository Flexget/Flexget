from loguru import logger

from flexget import log, plugin
from flexget.config_schema import register_config_key
from flexget.event import event

logger = logger.bind(name='log_filter')


class MyFilter:
    def __init__(self, config):
        self.config = config

    def __call__(self, record):
        for filter_config in self.config:
            if filter_config.get('plugin') and filter_config['plugin'] != record['name']:
                continue
            if filter_config.get('task') and filter_config['task'] != record['extra'].get('task'):
                continue
            if filter_config.get('message') and filter_config['message'] not in record['message']:
                continue
            if (
                filter_config.get('level')
                and filter_config['level'].upper() != record['level'].name
            ):
                continue
            return False
        return True


SCHEMA = {
    'type': 'array',
    'items': {
        'properties': {
            'plugin': {'type': 'string'},
            'message': {'type': 'string'},
            'task': {'type': 'string'},
            'level': {
                'type': 'string',
                'enum': [
                    'trace',
                    'debug',
                    'verbose',
                    'info',
                    'success',
                    'warning',
                    'error',
                    'critical',
                ],
            },
        },
        'minProperties': 1,
    },
    'minItems': 1,
}


class LogFilter(object):
    """
    Prevent entries with specific text from being logged.

    Example::
      log_filter:
      - message: in a galaxy
      - message: far far away
      - message: whatever text
      - message: what the heck?
        plugin: series

    """

    schema = SCHEMA

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_start(self, task, config):
        for filt in config:
            filt.setdefault('task', task.name)
        task.log_filter = MyFilter(config)
        logger.debug('Log filter added (config: {})', config)
        log.add_filter(task.log_filter)

    @plugin.priority(-255)
    def on_task_exit(self, task, config):
        if getattr(task, 'log_filter', None):
            log.remove_filter(task.log_filter)
            del task.log_filter

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(LogFilter, 'log_filter', api_ver=2)


@event('manager.startup')
def install_filters(manager):
    config = manager.config.get('log_filter')
    if not config:
        return
    logger.debug('Log filter added (config: {})', config)
    log.add_filter(MyFilter(config))


@event('config.register')
def register_config():
    register_config_key('log_filter', SCHEMA)
