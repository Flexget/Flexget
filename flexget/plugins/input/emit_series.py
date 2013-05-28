from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.entry import Entry
from flexget.plugin import register_plugin, DependencyError

log = logging.getLogger('emit_series')

try:
    from flexget.plugins.filter.series import Series, SeriesDatabase
except ImportError as e:
    log.error(e.message)
    raise DependencyError(issued_by='emit_series', missing='series')


class EmitSeries(SeriesDatabase):
    """
    Emit next episode number from all known series.

    Supports only series enumerated by season, episode.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_task_input(self, task, config):
        entries = []
        for series in task.session.query(Series).all():
            latest = self.get_latest_info(series)
            if not latest:
                # no latest known episode, skip
                continue

            # try next episode (eg. S01E02)
            title = '%s S%02dE%02d' % (series.name, latest['season'], latest['episode'] + 1)
            entries.append(Entry(title=title, url='',
                                 series_name=series.name,
                                 series_season=latest['season'],
                                 series_episode=latest['episode'] + 1))

            # different syntax (eg. 01x02)
            title = '%s %02dx%02d' % (series.name, latest['season'], latest['episode'] + 1)
            entries.append(Entry(title=title, url='',
                                 series_name=series.name,
                                 series_season=latest['season']+1,
                                 series_episode=1))

            # try next season
            title = '%s S%02dE%02d' % (series.name, latest['season'] + 1, 1)
            entries.append(Entry(title=title, url='',
                                 series_name=series.name,
                                 series_season=latest['season']+1,
                                 series_episode=1))

        return entries


register_plugin(EmitSeries, 'emit_series', api_ver=2)
