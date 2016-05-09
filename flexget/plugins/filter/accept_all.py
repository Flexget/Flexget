from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('accept_all')


class FilterAcceptAll(object):
    """
        Just accepts all entries.

        Example::

          accept_all: true
    """

    schema = {'type': 'boolean'}

    def on_task_filter(self, task, config):
        if config:
            for entry in task.entries:
                entry.accept()


@event('plugin.register')
def register_plugin():
    plugin.register(FilterAcceptAll, 'accept_all', api_ver=2)
