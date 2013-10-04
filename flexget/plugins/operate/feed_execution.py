from __future__ import unicode_literals, division, absolute_import
import fnmatch
import logging

from flexget import options, plugin
from flexget.event import event
from flexget.utils.tools import console

log = logging.getLogger('task_control')


@event('manager.execute.started')
def validate_cli_opts(manager):
    if not manager.options.execute.onlytask:
        return
    # Make a list of the specified tasks to run, and those available
    onlytasks = manager.options.execute.onlytask

    # Make sure the specified tasks exist
    for onlytask in onlytasks:
        if onlytask.lower() not in manager.tasks:
            if any(i in onlytask for i in '*?['):
                # Try globbing
                if any(fnmatch.fnmatchcase(f.lower(), onlytask.lower()) for f in manager.tasks):
                    continue
                console('No match for task pattern \'%s\'' % onlytask)
            else:
                console('Could not find task \'%s\'' % onlytask)
            manager.scheduler.shutdown(finish_queue=False)
            return


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

    @plugin.priority(255)
    def on_task_start(self, task):
        # If --task hasn't been specified don't do anything
        if not task.options.onlytask:
            return

        # Make a list of the specified tasks to run, and those available
        onlytasks = [t.lower() for t in task.options.onlytask]

        # If current task is not among the specified tasks, disable it
        if not (task.name.lower() in onlytasks or any(fnmatch.fnmatchcase(task.name.lower(), f) for f in onlytasks)):
            task.abort('not specified in --task', silent=True)


class ManualTask(object):
    """Only execute task when specified with --task"""

    schema = {'type': 'boolean'}

    @plugin.priority(255)
    def on_task_start(self, task, config):
        # Make sure we need to run
        if not config:
            return
        # If --task hasn't been specified disable this plugin
        if not task.options.onlytask:
            log.debug('Disabling task %s' % task.name)
            task.abort('manual task not specified in --task', silent=True)


@event('plugin.register')
def register_plugin():
    plugin.register(OnlyTask, '--task', builtin=True)
    plugin.register(ManualTask, 'manual', api_ver=2)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument('--task', dest='onlytask', nargs='+', metavar='TASK',
                                               help='run only specified task(s), optionally using glob patterns '
                                                    '("tv-*"). Matching is case-insensitive')
