from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='only_new')


class FilterOnlyNew:
    """Causes input plugins to only emit entries that haven't been seen on previous runs."""

    schema = {'type': 'boolean'}

    def on_task_start(self, task, config):
        """Make sure the remember_rejected plugin is available"""
        # Raises an error if plugin isn't available
        plugin.get('remember_rejected', self)

    # This should run after other learn plugins, so they know whether entries were _really_ accepted or rejected.
    # If they run after this, they will think everything has been rejected.
    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_learn(self, task, config):
        """Reject all entries so remember_rejected will reject them next time"""
        if not config or not task.entries:
            return
        logger.verbose(
            'Rejecting entries after the task has run so they are not processed next time.'
        )
        for entry in task.all_entries:
            entry.reject('Already processed entry', remember=True)


@event('plugin.register')
def register_plugin():
    plugin.register(FilterOnlyNew, 'only_new', api_ver=2)
