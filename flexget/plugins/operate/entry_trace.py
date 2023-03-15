from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='entry_trace')


def on_entry_action(entry, act=None, task=None, reason=None, **kwargs):
    entry[act.lower() + '_by'] = task.current_plugin
    entry.pop('reason', None)
    if reason:
        entry['reason'] = reason


class EntryOperations:
    """
    Records accept, reject and fail metainfo into entries.

    Creates fields::

      accepted_by: <plugin name>
      rejected_by: <plugin name>
      failed_by: <plugin name>

      reason: <given message by plugin>
    """

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_input(self, task, config):
        for entry in task.all_entries:
            entry.on_accept(on_entry_action, act='accepted', task=task)
            entry.on_reject(on_entry_action, act='rejected', task=task)
            entry.on_fail(on_entry_action, act='failed', task=task)


@event('plugin.register')
def register_plugin():
    plugin.register(EntryOperations, 'entry_operations', builtin=True, api_ver=2)
