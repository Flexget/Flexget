from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import copy
import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

log = logging.getLogger('run_task')


class RunTask(object):
    schema = {
        'type': 'object',
        'properties': {
            'task': one_or_more({'type': 'string'}),
            'when': one_or_more({'type': 'string',
                                 'enum': ['accepted', 'rejected', 'failed', 'no_entries', 'aborted', 'always']})
        },
        'required': ['task'],
        'additionalProperties': False
    }

    def prepare_config(self, config):
        tasks = config['task']
        if not isinstance(tasks, list):
            config['task'] = [tasks]

        config.setdefault('when', ['always'])

        when = config['when']
        if when and not isinstance(when, list):
            config['when'] = [when]

        return config

    def on_task_exit(self, task, config):
        config = self.prepare_config(config)
        conditions = [
            task.accepted and 'accepted' in config['when'],
            task.rejected and 'rejected' in config['when'],
            task.failed and 'failed' in config['when'],
            not task.all_entries and 'no_entries' in config['when'],
            'always' in config['when']
        ]
        if any(conditions):
            self.run_tasks(task, config['task'])

    def on_task_abort(self, task, config):
        config = self.prepare_config(config)
        if 'aborted' in config['when']:
            self.run_tasks(task, config['task'])

    def run_tasks(self, current_task, tasks):
        log.info('Scheduling tasks %s to run', tasks)
        options = copy.copy(current_task.options)
        options.tasks = tasks
        current_task.manager.execute(options=options)


@event('plugin.register')
def register_plugin():
    plugin.register(RunTask, 'run_task', api_ver=2)
