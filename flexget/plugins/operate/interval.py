import datetime

from loguru import logger

from flexget import options, plugin
from flexget.config_schema import parse_interval
from flexget.event import event

logger = logger.bind(name='interval')


class PluginInterval:
    """
        Allows specifying minimum interval for task execution.

        Format: [n] [minutes|hours|days|weeks]

        Example:

        interval: 7 days
    """

    schema = {'type': 'string', 'format': 'interval'}

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_start(self, task, config):
        if task.options.learn:
            logger.info('Ignoring task {} interval for --learn', task.name)
            return
        last_time = task.simple_persistence.get('last_time')
        if not last_time:
            logger.info('No previous run recorded, running now')
        elif task.options.interval_ignore:
            logger.info('Ignoring interval because of --now')
        else:
            logger.debug('last_time: {!r}', last_time)
            logger.debug('interval: {}', config)
            next_time = last_time + parse_interval(config)
            logger.debug('next_time: {!r}', next_time)
            if datetime.datetime.now() < next_time:
                logger.verbose(
                    'Interval {} not met on task {}. Use --now to override.', config, task.name
                )
                task.abort('Interval not met', silent=True)
                return
        logger.debug('interval passed')
        task.simple_persistence['last_time'] = datetime.datetime.now()


@event('plugin.register')
def register_plugin():
    plugin.register(PluginInterval, 'interval', api_ver=2)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument(
        '--now',
        action='store_true',
        dest='interval_ignore',
        default=False,
        help='run task(s) even if the interval plugin would normally prevent it',
    )
