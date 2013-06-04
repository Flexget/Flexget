from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.entry import Entry
from flexget.plugin import register_plugin, DependencyError

log = logging.getLogger('emit_series')

try:
    from flexget.plugins.filter.series import SeriesTask, SeriesDatabase
except ImportError as e:
    log.error(e.message)
    raise DependencyError(issued_by='emit_series', missing='series')

# TODO: Make this plugin awesome

class EmitSeries(SeriesDatabase):
    """
    Emit next episode number from all series configured in this task.

    Supports only series enumerated by season, episode.
    """

    schema = {'type': 'boolean'}

    def search_strings(self, series, season, episode):
        return ['%s S%02dE%02d' % (series, season, episode),
                '%s %02dx%02d' % (series, season, episode)]

    def on_task_input(self, task, config):
        if not config:
            return
        entries = []
        for seriestask in task.session.query(SeriesTask).filter(SeriesTask.name == task.name).all():
            series = seriestask.series
            latest = self.get_latest_info(series)
            if not latest:
                # no latest known episode, skip
                continue

            # try next episode and next season
            for season, episode in [(latest['season'], latest['episode'] + 1), (latest['season'] + 1, 1)]:
                search_strings = self.search_strings(series.name, season, episode)
                entries.append(Entry(title=search_strings[0], url='',
                                     search_strings=search_strings,
                                     series_name=series.name,
                                     series_season=season,
                                     series_episode=episode,
                                     series_id='S%02dE%02d' % (season, episode)))

        return entries


register_plugin(EmitSeries, 'emit_series', api_ver=2)
