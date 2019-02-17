from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

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

    schema = {'type': 'integer', 'minimum': 1}

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_filter(self, task, config):
        if task.options.learn:
            log.info('Plugin limit_new is disabled with --learn')
            return

        amount = config
        for index, entry in enumerate(task.accepted):
            if index < amount:
                log.verbose('Allowed %s (%s)' % (entry['title'], entry['url']))
            else:
                entry.reject('limit exceeded')
                # Also save this in backlog so that it can be accepted next time.
                plugin.get('backlog', self).add_backlog(task, entry)

        log.debug(
            'Rejected: %s Allowed: %s' % (len(task.accepted[amount:]), len(task.accepted[:amount]))
        )


@event('plugin.register')
def register_plugin():
    plugin.register(FilterLimitNew, 'limit_new', api_ver=2)
