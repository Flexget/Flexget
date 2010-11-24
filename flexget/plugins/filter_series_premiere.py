from flexget.plugin import register_plugin, priority, get_plugin_by_name
from flexget.plugins.filter_series import FilterSeriesBase


class FilterSeriesPremiere(FilterSeriesBase):
    """
    Accept an entry that appears to be the first episode of any series.

    Can be configured with any of the options of series plugin
    Examples:

    series_premiere: yes

    series_premiere:
      path: ~/Media/TV/_NEW_/.
      quality: 720p
      timeframe: 12 hours

    NOTE: this plugin only looks in the entry title and expects the title
    format to start with the series name followed by the episode info. Use
    the manipulate plugin to modify the entry title to match this format, if
    necessary.

    TODO:
        - integrate thetvdb to allow refining by genres, etc.
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
        config = feed.config['series_premiere']
        if not config:
            # Don't run when we are disabled
            return
        # Generate the group settings for series plugin
        group_settings = {}
        if isinstance(config, dict):
            group_settings = config
        group_settings['series_guessed'] = True
        # Generate a list of unique series that have premieres
        metainfo_series = get_plugin_by_name('metainfo_series')
        guess_entry = metainfo_series.instance.guess_entry
        guessed_series = set()
        for entry in feed.entries:
            if guess_entry(entry):
                if entry['series_id'] == 'S01E01':
                    guessed_series.add(entry['series_name'])
        # Reject any further episodes in those series
        for entry in feed.entries:
            for series in guessed_series:
                if entry.get('series_name') == series and entry.get('series_id') != 'S01E01':
                    feed.reject(entry, 'Non premiere episode in a premiere series')
        # Combine settings and series into series plugin config format
        allseries = {'settings': {'series_premiere': group_settings}, 'series_premiere': list(guessed_series)}
        # Merge the our config in to the main series config
        self.merge_config(feed, allseries)


register_plugin(FilterSeriesPremiere, 'series_premiere')
