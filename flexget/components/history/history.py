from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from . import db

log = logging.getLogger('history')


class PluginHistory(object):
    """Records all accepted entries for later lookup"""

    schema = {'type': 'boolean'}

    def on_task_learn(self, task, config):
        """Add accepted entries to history"""
        if config is False:
            return  # Explicitly disabled with configuration

        for entry in task.accepted:
            item = db.History()
            item.task = task.name
            item.filename = entry.get('output', None)
            item.title = entry['title']
            item.url = entry['url']
            reason = ''
            if 'reason' in entry:
                reason = ' (reason: %s)' % entry['reason']
            item.details = 'Accepted by %s%s' % (entry.get('accepted_by', '<unknown>'), reason)
            task.session.add(item)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginHistory, 'history', builtin=True, api_ver=2)
