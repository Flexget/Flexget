from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('entry_trace')


def on_entry_action(entry, act=None, task=None, reason=None, **kwargs):
    entry[act.lower() + '_by'] = task.current_plugin
    entry.pop('reason', None)
    if reason:
        entry['reason'] = reason


def on_entry_reset(entry):
    """Remove the metainfo we added to the entry."""
    entry.pop('accepted_by', None)
    entry.pop('rejected_by', None)
    entry.pop('failed_by', None)
    entry.pop('reason', None)


class EntryOperations(object):
    """
    Records accept, reject and fail metainfo into entries.

    Creates fields::

      accepted_by: <plugin name>
      rejected_by: <plugin name>
      failed_by: <plugin name>

      reason: <given message by plugin>
    """

    @plugin.priority(-255)
    def on_task_input(self, task, config):
        for entry in task.all_entries:
            entry.on_accept(on_entry_action, act='accepted', task=task)
            entry.on_reject(on_entry_action, act='rejected', task=task)
            entry.on_fail(on_entry_action, act='failed', task=task)
            entry.on_reset(on_entry_reset)


@event('plugin.register')
def register_plugin():
    plugin.register(EntryOperations, 'entry_operations', builtin=True, api_ver=2)
