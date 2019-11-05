from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.task import Task
from flexget.utils.cached_input import cached


log = logging.getLogger('subtask')


class Subtask(object):
    """An input plugin which returns accepted entries from another task."""

    schema = {'type': 'string'}

    @cached('subtask')
    def on_task_input(self, task, config):
        subtask_name = config
        subtask_config = task.manager.config['tasks'].get(subtask_name, {})
        # TODO: This seen disabling is super hacky, is there a better way?
        if 'seen' not in subtask_config:
            if isinstance(subtask_config.get('disable'), str):
                subtask_config['disable'] = [subtask_config['disable']]
            subtask_config.setdefault('disable', []).append('seen')
        input_task = Task(
            task.manager,
            '{}.{}'.format(task.name, subtask_name),
            config=subtask_config,
            # TODO: Do we want to pass all options through? Things like inject don't make sense, but perhaps others do.
            options=task.options,
            output=task.output,
            loglevel=task.loglevel,
            priority=task.priority,
            suppress_warnings=task.suppress_warnings,
        )
        log.verbose('Running task `%s` as subtask.', subtask_name)
        input_task.execute()
        log.verbose('Finished running subtask `%s`.', subtask_name)
        # Create fresh entries to reset state and strip association to old task
        return [Entry(e) for e in input_task.accepted]


@event('plugin.register')
def register_plugin():
    plugin.register(Subtask, 'subtask', api_ver=2)
