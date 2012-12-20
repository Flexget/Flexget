from __future__ import unicode_literals, division, absolute_import
from flexget.plugin import register_plugin, priority
import logging

log = logging.getLogger('details')


class PluginDetails(object):

    def on_task_start(self, task):
        # Make a flag for tasks to declare if it is ok not to produce entries
        task.no_entries_ok = False

    @priority(-512)
    def on_task_input(self, task):
        if not task.entries:
            if task.no_entries_ok:
                log.verbose('Task didn\'t produce any entries.')
            else:
                log.verbose('Task didn\'t produce any entries. This is likely due to a mis-configured or non-functional input.')
        else:
            log.verbose('Produced %s entries.' % (len(task.entries)))

    @priority(-512)
    def on_task_download(self, task):
        # Needs to happen as the first in download, so it runs after urlrewrites
        # and IMDB queue acceptance.
        log.verbose('Summary - Accepted: %s (Rejected: %s Undecided: %s Failed: %s)' %
            (len(task.accepted), len(task.rejected),
            len(task.entries) - len(task.accepted), len(task.failed)))


register_plugin(PluginDetails, 'details', builtin=True)
