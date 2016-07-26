from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('reject_all')


class FilterRejectAll(object):
    """
        Rejects all entries. Use for dev purposes.
        Sets expiration to 1 hour.

        Example::

          reject_all: yes
    """

    schema = {'type': 'boolean'}

    def on_task_filter(self, task, config):
        if config:
            for entry in task.entries:
                entry.reject(remember_time='1 hour')


@event('plugin.register')
def register_plugin():
    plugin.register(FilterRejectAll, 'reject_all', api_ver=2)
