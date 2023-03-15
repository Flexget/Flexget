from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='limit_new')


class FilterLimitNew:
    """
    Limit number of new items.

    Example::

      limit_new: 1

    This would allow only one new item to pass trough per execution.
    Useful for passing torrents slowly into download.

    Note that since this is per execution, actual rate depends how often
    FlexGet is executed.
    """

    schema = {'type': 'integer', 'minimum': 1}

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_filter(self, task, config):
        if task.options.learn:
            logger.info('Plugin limit_new is disabled with --learn')
            return

        amount = config
        for index, entry in enumerate(task.accepted):
            if index < amount:
                logger.verbose('Allowed {} ({})', entry['title'], entry['url'])
            else:
                entry.reject('limit exceeded')
                # Also save this in backlog so that it can be accepted next time.
                plugin.get('backlog', self).add_backlog(task, entry)

        logger.debug(
            'Rejected: {} Allowed: {}', len(task.accepted[amount:]), len(task.accepted[:amount])
        )


@event('plugin.register')
def register_plugin():
    plugin.register(FilterLimitNew, 'limit_new', api_ver=2)
