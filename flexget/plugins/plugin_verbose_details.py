from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('details')


class PluginDetails(object):

    def on_task_start(self, task, config):
        # Make a flag for tasks to declare if it is ok not to produce entries
        task.no_entries_ok = False

    @plugin.priority(-512)
    def on_task_input(self, task, config):
        if not task.entries:
            if task.no_entries_ok:
                log.verbose('Task didn\'t produce any entries.')
            else:
                log.warning('Task didn\'t produce any entries. This is likely due to a mis-configured or non-functional input.')
        else:
            log.verbose('Produced %s entries.' % (len(task.entries)))

    @plugin.priority(-512)
    def on_task_download(self, task, config):
        # Needs to happen as the first in download, so it runs after urlrewrites
        # and IMDB queue acceptance.
        log.verbose('Summary - Accepted: %s (Rejected: %s Undecided: %s Failed: %s)' %
            (len(task.accepted), len(task.rejected),
            len(task.entries) - len(task.accepted), len(task.failed)))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginDetails, 'details', builtin=True, api_ver=2)
