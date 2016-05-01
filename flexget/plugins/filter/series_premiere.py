from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.series import FilterSeriesBase, normalize_series_name, Series


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

    @property
    def schema(self):
        settings = self.settings_schema
        settings['properties']['allow_seasonless'] = {'type': 'boolean'}
        settings['properties']['allow_teasers'] = {'type': 'boolean'}
        return {'anyOf': [{'type': 'boolean'}, settings]}

    # Run after series and metainfo series plugins
    @plugin.priority(115)
    def on_task_metainfo(self, task, config):
        if not config:
            # Don't run when we are disabled
            return
        if task.is_rerun:
            return
        # Generate the group settings for series plugin
        group_settings = {}
        allow_seasonless = False
        desired_eps = [0, 1]
        if isinstance(config, dict):
            allow_seasonless = config.pop('allow_seasonless', False)
            if not config.pop('allow_teasers', True):
                desired_eps = [1]
            group_settings = config
        group_settings['identified_by'] = 'ep'
        # Generate a list of unique series that have premieres
        metainfo_series = plugin.get_plugin_by_name('metainfo_series')
        guess_entry = metainfo_series.instance.guess_entry
        # Make a set of unique series according to series name normalization rules
        guessed_series = {}
        for entry in task.entries:
            if guess_entry(entry, allow_seasonless=allow_seasonless, config=group_settings):
                if entry['series_season'] == 1 and entry['series_episode'] in desired_eps:
                    normalized_name = normalize_series_name(entry['series_name'])
                    db_series = task.session.query(Series).filter(Series.name == normalized_name).first()
                    if db_series and db_series.in_tasks:
                        continue
                    guessed_series.setdefault(normalized_name, entry['series_name'])
        # Reject any further episodes in those series
        for entry in task.entries:
            for series in guessed_series.values():
                if entry.get('series_name') == series and not (
                        entry.get('series_season') == 1 and
                        entry.get('series_episode') in desired_eps):
                    entry.reject('Non premiere episode in a premiere series')
        # Since we are running after task start phase, make sure not to merge into the config multiple times on reruns
        if not task.is_rerun:
            # Combine settings and series into series plugin config format
            allseries = {'settings': {'series_premiere': group_settings}, 'series_premiere': list(guessed_series.values())}
            # Merge the our config in to the main series config
            self.merge_config(task, allseries)


@event('plugin.register')
def register_plugin():
    plugin.register(FilterSeriesPremiere, 'series_premiere', api_ver=2)
