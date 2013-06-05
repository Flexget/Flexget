from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.plugin import register_plugin, priority

log = logging.getLogger('entry_trace')


def on_entry_action(entry, action=None, task=None, reason=None, **kwargs):
    entry[action.lower() + '_by'] = task.current_plugin
    entry.pop('reason', None)
    if reason:
        entry['reason'] = reason


class EntryOperations(object):
    """
    Records accept, reject and fail metainfo into entries.

    Creates fields::

      accepted_by: <plugin name>
      rejected_by: <plugin name>
      failed_by: <plugin name>

      reason: <given message by plugin>
    """

    @priority(-255)
    def on_task_input(self, task, config):
        for entry in task.all_entries:
            entry.on_accept(on_entry_action, action='accepted', task=task)
            entry.on_reject(on_entry_action, action='rejected', task=task)
            entry.on_fail(on_entry_action, action='failed', task=task)


register_plugin(EntryOperations, 'entry_operations', builtin=True, api_ver=2)
