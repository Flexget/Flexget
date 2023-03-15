from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='details')


class PluginDetails:
    def on_task_start(self, task, config):
        # Make a flag for tasks to declare if it is ok not to produce entries
        task.no_entries_ok = False

    @plugin.priority(-512)
    def on_task_input(self, task, config):
        if not task.entries:
            if task.no_entries_ok:
                logger.verbose('Task didn\'t produce any entries.')
            else:
                logger.warning(
                    "Task didn't produce any entries. "
                    "This is likely due to a mis-configured or non-functional input."
                )
        else:
            logger.verbose('Produced {} entries.', len(task.entries))

    @plugin.priority(-512)
    def on_task_download(self, task, config):
        # Needs to happen as the first in download, so it runs after urlrewrites
        # and IMDB queue acceptance.
        logger.verbose(
            'Summary - Accepted: {} (Rejected: {} Undecided: {} Failed: {})',
            len(task.accepted),
            len(task.rejected),
            len(task.undecided),
            len(task.failed),
        )


class NoEntriesOk:
    """Allows manually silencing the warning message for tasks that regularly produce no entries."""

    schema = {'type': 'boolean'}

    # Run after details plugin task_start
    @plugin.priority(127)
    def on_task_start(self, task, config):
        task.no_entries_ok = config


@event('plugin.register')
def register_plugin():
    plugin.register(PluginDetails, 'details', builtin=True, api_ver=2)
    plugin.register(NoEntriesOk, 'no_entries_ok', api_ver=2)
