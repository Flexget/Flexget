from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, priority, DependencyError, get_plugin_by_name

log = logging.getLogger('limit_new')


class FilterLimitNew(object):
    """
    Limit number of new items.

    Example::

      limit_new: 1

    This would allow only one new item to pass trough per execution.
    Useful for passing torrents slowly into download.

    Note that since this is per execution, actual rate depends how often
    FlexGet is executed.
    """

    schema = {
        'type': 'integer',
        'minimum': 1
    }

    def __init__(self):
        self.backlog = None

    def on_process_start(self, task, config):
        try:
            self.backlog = get_plugin_by_name('backlog').instance
        except DependencyError:
            log.warning('Unable utilize backlog plugin, entries may slip trough limit_new in some rare cases')

    @priority(-255)
    def on_task_filter(self, task, config):
        if task.manager.options.learn:
            log.info('Plugin limit_new is disabled with --learn / --reset')
            return

        amount = config
        for index, entry in enumerate(task.accepted):
            if index < amount:
                log.verbose('Allowed %s (%s)' % (entry['title'], entry['url']))
            else:
                entry.reject('limit exceeded')
                # Also save this in backlog so that it can be accepted next time.
                if self.backlog:
                    self.backlog.add_backlog(task, entry)

        log.debug('Rejected: %s Allowed: %s' % (len(task.accepted[amount:]), len(task.accepted[:amount])))


register_plugin(FilterLimitNew, 'limit_new', api_ver=2)
