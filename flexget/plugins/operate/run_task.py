from __future__ import unicode_literals, division, absolute_import

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event


class RunTask(object):
    schema = {
        'type': 'object',
        'properties': {
            'task': {'type': 'string'},
            'when': one_or_more({'type': 'string', 'enum': ['accepted', 'rejected', 'failed', 'no_entries', 'aborted']})
        },
        'required': ['task', 'when'],
        'additionalProperties': False
    }

    def on_task_exit(self, task, config):
        if task.accepted and 'accepted' in config['when']:
            task.manager.scheduler.execute(config['task'])
        elif task.rejected and 'rejected' in config['when']:
            task.manager.scheduler.execute(config['task'])
        elif task.failed and 'rejected' in config['when']:
            task.manager.scheduler.execute(config['task'])
        elif not task.all_entries and 'no_entries' in config['when']:
            task.manager.scheduler.execute(config['task'])

    def on_task_abort(self, task, config):
        if 'aborted' in config:
            task.manager.scheduler.execute(config['task'])


@event('plugin.register')
def register_plugin():
    plugin.register(RunTask, 'run_task', api_ver=2)
