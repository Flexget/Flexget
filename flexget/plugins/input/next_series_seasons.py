from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.manager import Session
from flexget.plugins.filter.series import SeriesTask, Series, get_latest_release, get_latest_season_pack_release
from flexget.plugins.filter.series import get_latest_episode_release

plugin_name = 'next_series_seasons'
log = logging.getLogger(plugin_name)

MAX_SEASON_DIFF_WITHOUT_BEGIN = 15
MAX_SEASON_DIFF_WITH_BEGIN = 30

class NextSeriesSeasons(object):
    """
    Emit next season number from all series configured in this task.

    Supports only 'ep' mode series.
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

    def __init__(self):
        self.rerun_entries = []

    def season_identifiers(self, season):
        return ['S%02d' % season]

    def search_entry(self, series, season, task, rerun=True):
        # Extract the alternate names for the series
        alts = [alt.alt_name for alt in series.alternate_names]
        # Also consider series name without parenthetical (year, country) an alternate name
        paren_match = re.match(r'(.+?)( \(.+\))?$', series.name)
        if paren_match.group(2):
            alts.append(paren_match.group(1))
        search_strings = ['%s %s' % (series.name, id) for id in self.season_identifiers(season)]
        series_id = 'S%02d' % season
        for alt in alts:
            search_strings.extend(['%s %s' % (alt, id) for id in self.season_identifiers(season)])
        entry = Entry(title=search_strings[0], url='',
                      search_strings=search_strings,
                      series_name=series.name,
                      series_alternate_names=alts,  # Not sure if this field is useful down the road.
                      series_season=season,
                      season_pack_lookup=True,
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

        if task.is_rerun:
            # Just return calculated next eps on reruns
            entries = self.rerun_entries
            self.rerun_entries = []
            return entries
        else:
            self.rerun_entries = []

        entries = []
        impossible = {}
        with Session() as session:
            for seriestask in session.query(SeriesTask).filter(SeriesTask.name == task.name).all():
                series = seriestask.series
                log.trace('evaluating %s', series.name)
                if not series:
                    # TODO: How can this happen?
                    log.debug('Found SeriesTask item without series specified. Cleaning up.')
                    session.delete(seriestask)
                    continue

                if series.identified_by not in ['ep']:
                    log.trace('unsupported identified_by scheme')
                    reason = series.identified_by or 'auto'
                    impossible.setdefault(reason, []).append(series.name)
                    continue

                low_season = 0
                # Don't look for seasons older than begin ep
                if series.begin and series.begin.season and series.begin.season > 1:
                    low_season = max(series.begin.season - 1, 0)

                new_season = None
                check_downloaded = not config.get('backfill')
                latest_season = get_latest_release(series, downloaded=check_downloaded)
                if latest_season:
                    if latest_season.season <= low_season:
                        latest_season = new_season = low_season + 1
                    elif latest_season.season in series.completed_seasons:
                        latest_season = new_season = latest_season.season + 1
                    else:
                        latest_season = latest_season.season
                else:
                    latest_season = low_season + 1

                if (latest_season - low_season > MAX_SEASON_DIFF_WITHOUT_BEGIN and not series.begin) or (series.begin and
                    latest_season - series.begin.season > MAX_SEASON_DIFF_WITH_BEGIN):
                    if series.begin:
                        log.error('Series `%s` has a begin episode set (`%s`), but the season currently being processed '
                                  '(%s) is %s seasons later than it. To prevent emitting incorrect seasons, this ' 
                                  'series will not emit unless the begin episode is adjusted to a season that is less '
                                  'than %s seasons from season %s.', series.name, series.begin.identifier, latest_season,
                                  (latest_season - series.begin.season), MAX_SEASON_DIFF_WITH_BEGIN, latest_season)
                    else:
                        log.error('Series `%s` does not have a begin episode set and continuing this task would result '                                   'in more than %s seasons being emitted. To prevent emitting incorrect seasons, this '
                                  'series will not emit unless the begin episode is set in your series config or by '
                                  'using the CLI subcommand `series begin "%s" <SxxExx>`.', series.name,
                                  MAX_SEASON_DIFF_WITHOUT_BEGIN, series.name)
                    continue
                for season in range(latest_season, low_season, -1):
                    if season in series.completed_seasons:
                        log.debug('season %s is marked as completed, skipping', season)
                        continue
                    log.trace('Evaluating season %s for series `%s`', season, series.name)
                    latest = get_latest_release(series, season=season, downloaded=check_downloaded)
                    if series.begin and season == series.begin.season and (not latest or latest < series.begin):
                        # In case series.begin season is already completed, look in next available season
                        lookup_season = series.begin.season
                        while lookup_season in series.completed_seasons:
                            lookup_season += 1
                        entries.append(self.search_entry(series, lookup_season, task))
                    elif latest:
                        entries.append(self.search_entry(series, latest.season, task))
                    # First iteration of a new season with no show begin and show has downloads
                    elif new_season and season == new_season:
                        entries.append(self.search_entry(series, season, task))
                    else:
                        if config.get('from_start') or config.get('backfill'):
                            entries.append(self.search_entry(series, season, task))
                        else:
                            log.verbose('Series `%s` has no history. Set the begin option in your config, '
                                        'or use the CLI subcommand `series begin "%s" <SxxExx>` '
                                        'to set the first episode to emit', series.name, series.name)
                            break
                    # Skip older seasons if we are not in backfill mode
                    if not config.get('backfill'):
                        log.debug('backfill is not enabled; skipping older seasons')
                        break

        for reason, series in impossible.items():
            log.verbose('Series `%s` with identified_by value `%s` are not supported. ',
                        ', '.join(sorted(series)), reason)

        return entries

    def on_search_complete(self, entry, task=None, identified_by=None, **kwargs):
        """Decides whether we should look for next season based on whether we found/accepted any seasons."""
        with Session() as session:
            series = session.query(Series).filter(Series.name == entry['series_name']).first()
            latest = get_latest_season_pack_release(series)
            latest_ep = get_latest_episode_release(series, season=entry['series_season'])

            if entry.accepted:
                if not latest and latest_ep:
                    log.debug('season lookup produced an episode result; assuming no season match, no need to rerun')
                    return
                else:
                    log.debug('%s %s was accepted, rerunning to look for next season.', entry['series_name'],
                              entry['series_id'])
                    if not any(e.get('series_season') == latest.season + 1 for e in self.rerun_entries):
                        self.rerun_entries.append(self.search_entry(series, latest.season + 1, task))
                    # Increase rerun limit by one if we have matches, this way
                    # we keep searching as long as matches are found!
                    # TODO: this should ideally be in discover so it would be more generic
                    task.max_reruns += 1
                    task.rerun(plugin=plugin_name, reason='Look for next season')
            elif latest and not latest.completed:
                # There are known releases of this season, but none were accepted
                return


@event('plugin.register')
def register_plugin():
    plugin.register(NextSeriesSeasons, plugin_name, api_ver=2)
