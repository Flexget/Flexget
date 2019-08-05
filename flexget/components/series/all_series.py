from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event
from . import series as plugin_series


class FilterAllSeries(plugin_series.FilterSeriesBase):
    """
    Grabs all entries that appear to be series episodes in a task.

    This plugin just configures the series plugin dynamically with all series from the task.
    It can take any of the options of the series plugin.

    Example::
      all_series: yes

    ::
      all_series:
        quality: hdtv+
        propers: no
    """

    @property
    def schema(self):
        return {'oneOf': [{'type': 'boolean'}, self.settings_schema]}

    # Run after series and metainfo series plugins
    @plugin.priority(115)
    def on_task_metainfo(self, task, config):
        if not config:
            # Don't run when we are disabled
            return
        if task.is_rerun:
            # Since we are running after task start phase, make sure not to merge into the config again on reruns
            return
        # Generate the group settings for series plugin
        group_settings = {}
        if isinstance(config, dict):
            group_settings = config
        group_settings.setdefault('identified_by', 'auto')
        # Generate a list of unique series that metainfo_series can parse for this task
        guess_entry = plugin.get('metainfo_series', 'all_series').guess_entry
        guessed_series = {}
        for entry in task.entries:
            if guess_entry(entry, config=group_settings):
                guessed_series.setdefault(
                    plugin_series.normalize_series_name(entry['series_name']), entry['series_name']
                )
        # Combine settings and series into series plugin config format
        all_series = {
            'settings': {'all_series': group_settings},
            'all_series': list(guessed_series.values()),
        }
        # Merge our config in to the main series config
        self.merge_config(task, all_series)


@event('plugin.register')
def register_plugin():
    plugin.register(FilterAllSeries, 'all_series', api_ver=2)
