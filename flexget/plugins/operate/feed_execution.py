from __future__ import unicode_literals, division, absolute_import
import fnmatch
import logging

from flexget import options
from flexget.event import event
from flexget.plugin import register_plugin
from flexget.utils.tools import console

log = logging.getLogger('task_control')


@event('manager.startup')
def validate_cli_opts(manager):
    if manager.options.cli_command != 'execute' or not manager.options.execute.onlytask:
        return
    # Make a list of the specified tasks to run, and those available
    onlytasks = manager.options.execute.onlytask.split(',')

    # Make sure the specified tasks exist
    task_names = manager.config['tasks'].keys()
    for onlytask in onlytasks:
        if onlytask.lower() not in task_names:
            if any(i in onlytask for i in '*?['):
                # Try globbing
                if not any(fnmatch.fnmatchcase(f.lower(), onlytask.lower()) for f in task_names):
                    console('No match for task pattern \'%s\'' % onlytask)
                    manager.shutdown(finish_queue=False)
                    return
            else:
                console('Could not find task \'%s\'' % onlytask)
            manager.shutdown(finish_queue=False)



class OnlyTask(object):
    """
    Implements --task option to only run specified task(s)

    Example:
    flexget --task taska

    Multiple tasks:
    flexget --task taska,taskb

    Patterns:
    flexget --task 'tv*'
    """

    def on_task_prepare(self, task):
        # If --task hasn't been specified don't do anything
        if not task.options.onlytask:
            return

        # Make a list of the specified tasks to run, and those available
        onlytasks = [t.lower() for t in task.options.onlytask.split(',')]

        # If current task is not among the specified tasks, disable it
        if not (task.name.lower() in onlytasks or any(fnmatch.fnmatchcase(task.name.lower(), f) for f in onlytasks)):
            task.enabled = False


class ManualTask(object):
    """Only execute task when specified with --task"""

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_process_start(self, task):
        # Make sure we need to run
        if not task.config['manual']:
            return
        # If --task hasn't been specified disable this plugin
        if not task.options.onlytask:
            log.debug('Disabling task %s' % task.name)
            task.enabled = False


register_plugin(OnlyTask, '--task', builtin=True)
register_plugin(ManualTask, 'manual')


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument('--task', dest='onlytask', default=None, metavar='TASK[,...]',
                                               help='run only specified task(s), optionally using glob patterns '
                                                    '("tv-*"). Matching is case-insensitive')
