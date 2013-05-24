from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin

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

register_plugin(FilterAcceptAll, 'accept_all', api_ver=2)
