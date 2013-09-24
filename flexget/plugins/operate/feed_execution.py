from __future__ import unicode_literals, division, absolute_import
import fnmatch
import logging

from flexget.event import event
from flexget.plugin import register_plugin, PluginError

log = logging.getLogger('task_control')


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

    def on_process_start(self, task):
        # If --task hasn't been specified don't do anything
        if not task.manager.options.execute.onlytask:
            return

        # Make a list of the specified tasks to run, and those available
        onlytasks = task.manager.options.execute.onlytask.split(',')

        # Make sure the specified tasks exist
        enabled_tasks = [f.name.lower() for f in task.manager.tasks.itervalues() if f.enabled]
        for onlytask in onlytasks:
            if any(i in onlytask for i in '*?['):
                # Try globbing
                if not any(fnmatch.fnmatchcase(f.lower(), onlytask.lower()) for f in enabled_tasks):
                    task.manager.disable_tasks()
                    raise PluginError('No match for task pattern \'%s\'' % onlytask, log)
            elif onlytask.lower() not in enabled_tasks:
                # If any of the tasks do not exist, exit with an error
                task.manager.disable_tasks()
                raise PluginError('Could not find task \'%s\'' % onlytask, log)

        # If current task is not among the specified tasks, disable it
        if not any(task.name.lower() == f.lower() or fnmatch.fnmatchcase(task.name.lower(), f.lower())
                for f in onlytasks):
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
        if not task.manager.options.execute.onlytask:
            log.debug('Disabling task %s' % task.name)
            task.enabled = False


register_plugin(OnlyTask, '--task', builtin=True)
register_plugin(ManualTask, 'manual')


@event('register_parser_arguments')
def register_parser_arguments(core_parser):
    core_parser.get_subparser('execute').add_argument('--task', dest='onlytask', default=None, metavar='TASK[,...]',
                                                   help='run only specified task(s), optionally using glob patterns '
                                                        '("tv-*"). Matching is case-insensitive')
