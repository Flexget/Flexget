from __future__ import unicode_literals, division, absolute_import
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

    def on_task_start(self, task, config):
        # Can also be used to turn off the task auto_accept option from the config
        task.options.auto_accept = config

    def on_task_filter(self, task, config):
        if config:
            for entry in task.entries:
                entry.accept()

@event('plugin.register')
def register_plugin():
    plugin.register(FilterAcceptAll, 'accept_all', api_ver=2)
