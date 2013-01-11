from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.entry import Entry
from flexget.plugin import register_plugin, DependencyError

log = logging.getLogger('emit_series')

try:
    from flexget.plugins.filter.series import Series, Episode, SeriesDatabase
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

            # TODO: do this only after average time between episode has been passed since
            # last episode

            # try next episode (eg. S01E02)
            title = '%s S%02dE%02d' % (series.name, latest['season'], latest['episode'] + 1)
            task.entries.append(Entry(title=title, url=''))

            # different syntax (eg. 01x02)
            title = '%s %02dx%02d' % (series.name, latest['season'], latest['episode'] + 1)
            task.entries.append(Entry(title=title, url=''))

            # TODO: do this only if there hasn't been new episode in few weeks

            # try next season
            title = '%s S%02dE%02d' % (series.name, latest['season'] + 1, 1)
            task.entries.append(Entry(title=title, url=''))

        return entries


register_plugin(EmitSeries, 'emit_series', api_ver=2)
