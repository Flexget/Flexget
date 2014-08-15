from __future__ import unicode_literals, division, absolute_import
import copy
import functools
import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

log = logging.getLogger('run_task')


class RunTask(object):
    schema = {
        'type': 'object',
        'properties': {
            'task': {'type': 'string'},
            'when': one_or_more({'type': 'string',
                                 'enum': ['accepted', 'rejected', 'failed', 'no_entries', 'aborted', 'always']})
        },
        'required': ['task'],
        'additionalProperties': False
    }

    def on_task_exit(self, task, config):
        config.setdefault('when', 'always')
        conditions = [
            task.accepted and 'accepted' in config['when'],
            task.rejected and 'rejected' in config['when'],
            not task.all_entries and 'no_entries' in config['when'],
            'always' in config['when']
        ]
        if any(conditions):
            self.run_task(task, config['task'])

    def on_task_abort(self, task, config):
        if 'aborted' in config:
            self.run_task(task, config['task'])

    def run_task(self, current_task, run_task):
        log.info('Scheduling %s task to run' % run_task)
        options = copy.copy(current_task.options)
        options.tasks = [run_task]
        current_task.manager.execute(options=options)


@event('plugin.register')
def register_plugin():
    plugin.register(RunTask, 'run_task', api_ver=2)
