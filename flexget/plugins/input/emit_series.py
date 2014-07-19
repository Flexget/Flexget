from __future__ import unicode_literals, division, absolute_import
import logging

from sqlalchemy import desc, and_

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('emit_series')

try:
    from flexget.plugins.filter.series import SeriesTask, Series, Episode, Release, get_latest_release
except ImportError as e:
    log.error(e.message)
    raise plugin.DependencyError(issued_by='emit_series', missing='series')


class EmitSeries(object):
    """
    Emit next episode number from all series configured in this task.

    Supports only 'ep' and 'sequence' mode series.
    """

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'from_start': {'type': 'boolean', 'default': False},
                    'backfill': {'type': 'boolean', 'default': False}
                },
                'additionalProperties': False
            }
        ]
    }

    def ep_identifiers(self, season, episode):
        return ['S%02dE%02d' % (season, episode),
                '%dx%02d' % (season, episode)]

    def sequence_identifiers(self, episode):
        return ['%d' % episode,
                '%02d' % episode,
                '%03d' % episode]

    def search_entry(self, series, season, episode, task, rerun=True):
        if series.identified_by == 'ep':
            search_strings = ['%s %s' % (series.name, id) for id in self.ep_identifiers(season, episode)]
            series_id = 'S%02dE%02d' % (season, episode)
        else:
            search_strings = ['%s %s' % (series.name, id) for id in self.sequence_identifiers(episode)]
            series_id = episode
        entry = Entry(title=search_strings[0], url='',
                      search_strings=search_strings,
                      series_name=series.name,
                      series_season=season,
                      series_episode=episode,
                      series_id=series_id,
                      series_id_type=series.identified_by)
        if rerun:
            entry.on_complete(self.on_search_complete, task=task, identified_by=series.identified_by)
        return entry

    def on_task_input(self, task, config):
        if not config:
            return
        if isinstance(config, bool):
            config = {}
        if not task.is_rerun:
            self.try_next_season = {}
        entries = []
        for seriestask in task.session.query(SeriesTask).filter(SeriesTask.name == task.name).all():
            series = seriestask.series
            if not series:
                # TODO: How can this happen?
                log.debug('Found SeriesTask item without series specified. Cleaning up.')
                task.session.delete(seriestask)
                continue

            if series.identified_by not in ['ep', 'sequence']:
                log.verbose('Can only emit ep or sequence based series. `%s` is identified_by %s' %
                            (series.name, series.identified_by or 'auto'))
                continue

            low_season = 0 if series.identified_by == 'ep' else -1

            latest_season = get_latest_release(series)
            if latest_season:
                latest_season = latest_season.season
            else:
                latest_season = low_season + 1

            if self.try_next_season.get(series.name):
                entries.append(self.search_entry(series, latest_season + 1, 1, task))
            else:
                for season in xrange(latest_season, low_season, -1):
                    log.debug('Adding episodes for %d' % latest_season)
                    check_downloaded = not config.get('backfill')
                    latest = get_latest_release(series, season=season, downloaded=check_downloaded)
                    if series.begin and (not latest or latest < series.begin):
                        entries.append(self.search_entry(series, series.begin.season, series.begin.number, task))
                    elif latest:
                        start_at_ep = 1
                        episodes_this_season = (task.session.query(Episode).
                                                filter(Episode.series_id == series.id).
                                                filter(Episode.season == season))
                        if series.identified_by == 'sequence':
                            # Don't look for missing too far back with sequence shows
                            start_at_ep = max(latest.number - 10, 1)
                            episodes_this_season = episodes_this_season.filter(Episode.number >= start_at_ep)
                        latest_ep_this_season = episodes_this_season.order_by(desc(Episode.number)).first()
                        downloaded_this_season = (episodes_this_season.join(Episode.releases).
                                                filter(Release.downloaded == True).all())
                        # Calculate the episodes we still need to get from this season
                        if series.begin and series.begin.season == season:
                            start_at_ep = max(start_at_ep, series.begin.number)
                        eps_to_get = range(start_at_ep, latest_ep_this_season.number + 1)
                        for ep in downloaded_this_season:
                            try:
                                eps_to_get.remove(ep.number)
                            except ValueError:
                                pass
                        entries.extend(self.search_entry(series, season, x, task, rerun=False) for x in eps_to_get)
                        # If we have already downloaded the latest known episode, try the next episode
                        if latest_ep_this_season.releases:
                            entries.append(self.search_entry(series, season, latest_ep_this_season.number + 1, task))
                    else:
                        if config.get('from_start') or config.get('backfill'):
                            entries.append(self.search_entry(series, season, 1, task))
                        else:
                            log.verbose('Series `%s` has no history. Set begin option, or use CLI `series begin` '
                                        'subcommand to set first episode to emit' % series.name)
                            break

                    if not config.get('backfill'):
                        break

        return entries

    def on_search_complete(self, entry, task=None, identified_by=None, **kwargs):
        series = task.session.query(Series).filter(Series.name == entry['series_name']).first()
        latest = get_latest_release(series)
        episode = (task.session.query(Episode).join(Episode.series).
                   filter(Series.name == entry['series_name']).
                   filter(Episode.season == entry['series_season']).
                   filter(Episode.number == entry['series_episode']).
                   first())
        if entry.accepted or (episode and len(episode.releases) > 0):
            self.try_next_season.pop(entry['series_name'], None)
            task.rerun()
        elif latest and latest.season == entry['series_season']:
            if identified_by != 'ep':
                # Do not try next season if this is not an 'ep' show
                return
            if entry['series_name'] not in self.try_next_season:
                self.try_next_season[entry['series_name']] = True
                task.rerun()
            else:
                # Don't try a second time
                self.try_next_season[entry['series_name']] = False


@event('plugin.register')
def register_plugin():
    plugin.register(EmitSeries, 'emit_series', api_ver=2)
