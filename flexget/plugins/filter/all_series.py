from __future__ import unicode_literals, division, absolute_import
from flexget.plugin import register_plugin, priority, get_plugin_by_name
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
        min_quality: hdtv
        max_quality: 720p
        propers: no
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        # Accept yes to just turn on
        root.accept('boolean')
        options = root.accept('dict')
        self.build_options_validator(options)
        return root

    # Run after series and metainfo series plugins
    @priority(115)
    def on_task_metainfo(self, task, config):
        if not config:
            # Don't run when we are disabled
            return
        # Generate the group settings for series plugin
        group_settings = {}
        if isinstance(config, dict):
            group_settings = config
        # Generate a list of unique series that metainfo_series can parse for this task
        metainfo_series = get_plugin_by_name('metainfo_series')
        guess_entry = metainfo_series.instance.guess_entry
        guessed_series = {}
        for entry in task.entries:
            if guess_entry(entry):
                guessed_series.setdefault(normalize_series_name(entry['series_name']), entry['series_name'])
        # Combine settings and series into series plugin config format
        allseries = {'settings': {'all_series': group_settings}, 'all_series': guessed_series.values()}
        # Merge our config in to the main series config
        self.merge_config(task, allseries)


register_plugin(FilterAllSeries, 'all_series', api_ver=2)
