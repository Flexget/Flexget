from flexget.plugin import register_plugin, priority, get_plugin_by_name
from flexget.plugins.filter_series import FilterSeriesBase


class FilterAllSeries(FilterSeriesBase):
    """
    Grabs all entries that appear to be series episodes in a feed.

    This plugin just configures the series plugin dynamically with all series from the feed.
    It can take any of the options of the series plugin.
    Example:
    all_series: yes

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

    # Configure the series plugin before any filtering is done
    @priority(255)
    def on_feed_filter(self, feed):
        config = feed.config['all_series']
        if not config:
            # Don't run when we are disabled
            return
        # Generate the group settings for series plugin
        group_settings = {}
        if isinstance(config, dict):
            group_settings = config
        group_settings['series_guessed'] = True
        # Generate a list of unique series that metainfo_series can parse for this feed
        metainfo_series = get_plugin_by_name('metainfo_series')
        guess_entry = metainfo_series.instance.guess_entry
        guessed_series = set()
        for entry in feed.entries:
            if guess_entry(entry):
                guessed_series.add(entry['series_name'])
        # Combine settings and series into series plugin config format
        allseries = {'settings': {'all_series': group_settings}, 'all_series': list(guessed_series)}
        # Merge the our config in to the main series config
        self.merge_config(feed, allseries)


register_plugin(FilterAllSeries, 'all_series')
