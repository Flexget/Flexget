from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('imdb_required')


class FilterImdbRequired(object):
    """
    Rejects entries without imdb_url or imdb_id.
    Makes imdb lookup / search if necessary.

    Example::

      imdb_required: yes
    """

    schema = {'type': 'boolean'}

    @plugin.priority(32)
    def on_task_filter(self, task, config):
        if not config:
            return
        for entry in task.entries:
            try:
                plugin.get_plugin_by_name('imdb_lookup').instance.lookup(entry)
            except plugin.PluginError:
                entry.reject('imdb required')
            if 'imdb_id' not in entry and 'imdb_url' not in entry:
                entry.reject('imdb required')


@event('plugin.register')
def register_plugin():
    plugin.register(FilterImdbRequired, 'imdb_required', api_ver=2)
