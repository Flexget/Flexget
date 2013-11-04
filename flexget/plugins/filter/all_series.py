from __future__ import unicode_literals, division, absolute_import

from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.series import FilterSeriesBase, normalize_series_name


class FilterAllSeries(FilterSeriesBase):
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
        group_settings['identified_by'] = 'ep'
        # Generate a list of unique series that metainfo_series can parse for this task
        metainfo_series = plugin.get_plugin_by_name('metainfo_series')
        guess_entry = metainfo_series.instance.guess_entry
        guessed_series = {}
        for entry in task.entries:
            if guess_entry(entry):
                guessed_series.setdefault(normalize_series_name(entry['series_name']), entry['series_name'])
        # Combine settings and series into series plugin config format
        allseries = {'settings': {'all_series': group_settings}, 'all_series': guessed_series.values()}
        # Merge our config in to the main series config
        self.merge_config(task, allseries)


@event('plugin.register')
def register_plugin():
    plugin.register(FilterAllSeries, 'all_series', api_ver=2)
