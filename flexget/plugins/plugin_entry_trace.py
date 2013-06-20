from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.plugin import register_plugin

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

    def on_task_start(self, task, config):
        task.add_entry_hook('accept', on_entry_action, action='accepted', task=task)
        task.add_entry_hook('reject', on_entry_action, action='rejected', task=task)
        task.add_entry_hook('fail', on_entry_action, action='failed', task=task)


register_plugin(EntryOperations, 'entry_operations', builtin=True, api_ver=2)
