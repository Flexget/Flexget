from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, get_plugin_by_name

log = logging.getLogger('only_new')


class FilterOnlyNew(object):
    """Causes input plugins to only emit entries that haven't been seen on previous runs."""

    schema = {'type': 'boolean'}

    def on_process_start(self, task, config):
        """Make sure the remember_rejected plugin is available"""
        # Raises an error if plugin isn't available
        get_plugin_by_name('remember_rejected')

    def on_task_exit(self, task, config):
        """Reject all entries so remember_rejected will reject them next time"""
        if not config or not task.entries:
            return
        log.verbose('Rejecting entries after the task has run so they are not processed next time.')
        for entry in task.entries:
            entry.reject('Already processed entry', remember=True)


register_plugin(FilterOnlyNew, 'only_new', api_ver=2)
