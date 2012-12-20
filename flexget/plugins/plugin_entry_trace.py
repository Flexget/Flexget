from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin

log = logging.getLogger('entry_trace')


def entry_action_factory(action):

    def on_entry_action(self, task, entry, **kwargs):
        reason = kwargs.get('reason')
        task.trace(entry, '%s: %s' % (action.title(), reason or 'No reason specified'))
        entry[action.lower() + '_by'] = task.current_plugin
        entry.pop('reason', None)
        if reason:
            entry['reason'] = reason
    return on_entry_action


class PluginEntryTrace(object):
    """Records accept, reject and fail metainfo into entries."""

    on_entry_accept = entry_action_factory('accepted')
    on_entry_reject = entry_action_factory('rejected')
    on_entry_fail = entry_action_factory('failed')


register_plugin(PluginEntryTrace, 'entry_trace', builtin=True)
