from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, priority, get_plugin_by_name, PluginError

log = logging.getLogger('imdb_required')


class FilterImdbRequired(object):
    """
    Rejects entries without imdb_url or imdb_id.
    Makes imdb lookup / search if necessary.

    Example::

      imdb_required: yes
    """

    schema = {'type': 'boolean'}

    @priority(32)
    def on_task_filter(self, task):
        for entry in task.entries:
            try:
                get_plugin_by_name('imdb_lookup').instance.lookup(entry)
            except PluginError:
                entry.reject('imdb required')
            if 'imdb_url' not in entry and 'imdb_id' not in entry:
                entry.reject('imdb required')

register_plugin(FilterImdbRequired, 'imdb_required')
